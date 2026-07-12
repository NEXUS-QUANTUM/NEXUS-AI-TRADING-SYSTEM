/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import { cn } from '@/utils/helpers';
import { Button } from './Button';
import { ChevronDown, ChevronUp, X } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface DropdownProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  trigger?: React.ReactNode;
  children?: React.ReactNode;
  align?: 'start' | 'center' | 'end';
  side?: 'top' | 'bottom' | 'left' | 'right';
  sideOffset?: number;
  alignOffset?: number;
  className?: string;
  triggerClassName?: string;
  contentClassName?: string;
  disabled?: boolean;
  closeOnSelect?: boolean;
  closeOnEscape?: boolean;
  closeOnOutsideClick?: boolean;
  portal?: boolean;
  container?: HTMLElement | null;
  onEscapeKeyDown?: (event: KeyboardEvent) => void;
  onPointerDownOutside?: (event: Event) => void;
  onInteractOutside?: (event: Event) => void;
  onOpenAutoFocus?: (event: Event) => void;
  onCloseAutoFocus?: (event: Event) => void;
}

export interface DropdownItemProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
  inset?: boolean;
  icon?: React.ReactNode;
  shortcut?: string;
  variant?: 'default' | 'destructive' | 'success' | 'warning' | 'info';
  onSelect?: () => void;
}

export interface DropdownGroupProps {
  children?: React.ReactNode;
  className?: string;
  heading?: string;
}

export interface DropdownLabelProps {
  children?: React.ReactNode;
  className?: string;
  inset?: boolean;
}

export interface DropdownSeparatorProps {
  className?: string;
}

export interface DropdownItemGroupProps {
  children?: React.ReactNode;
  className?: string;
  heading?: string;
}

// ============================================
// CONTEXTE
// ============================================

interface DropdownContextType {
  open: boolean;
  setOpen: (open: boolean) => void;
  closeOnSelect: boolean;
  triggerRef: React.RefObject<HTMLDivElement>;
  contentRef: React.RefObject<HTMLDivElement>;
}

const DropdownContext = React.createContext<DropdownContextType | undefined>(
  undefined
);

const useDropdown = () => {
  const context = React.useContext(DropdownContext);
  if (!context) {
    throw new Error('useDropdown must be used within a Dropdown');
  }
  return context;
};

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

const Dropdown = React.forwardRef<HTMLDivElement, DropdownProps>(
  (
    {
      open: openProp,
      defaultOpen = false,
      onOpenChange,
      trigger,
      children,
      align = 'center',
      side = 'bottom',
      sideOffset = 4,
      alignOffset = 0,
      className,
      triggerClassName,
      contentClassName,
      disabled = false,
      closeOnSelect = true,
      closeOnEscape = true,
      closeOnOutsideClick = true,
      portal = true,
      container,
      onEscapeKeyDown,
      onPointerDownOutside,
      onInteractOutside,
      onOpenAutoFocus,
      onCloseAutoFocus,
      ...props
    },
    ref
  ) => {
    // ============================================
    // RÉFÉRENCES
    // ============================================
    const triggerRef = React.useRef<HTMLDivElement>(null);
    const contentRef = React.useRef<HTMLDivElement>(null);
    const [isOpen, setIsOpen] = React.useState(defaultOpen);

    // ============================================
    // EFFETS
    // ============================================
    React.useEffect(() => {
      if (openProp !== undefined) {
        setIsOpen(openProp);
      }
    }, [openProp]);

    // ============================================
    // FONCTIONS
    // ============================================
    const setOpen = React.useCallback(
      (newOpen: boolean) => {
        setIsOpen(newOpen);
        onOpenChange?.(newOpen);
      },
      [onOpenChange]
    );

    const toggle = React.useCallback(() => {
      if (disabled) return;
      setOpen(!isOpen);
    }, [isOpen, disabled, setOpen]);

    const handleSelect = React.useCallback(() => {
      if (closeOnSelect) {
        setOpen(false);
      }
    }, [closeOnSelect, setOpen]);

    // ============================================
    // GESTIONNAIRES DE CLAVIER
    // ============================================
    React.useEffect(() => {
      if (!isOpen || !closeOnEscape) return;

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          e.preventDefault();
          setOpen(false);
          onEscapeKeyDown?.(e);
        }
      };

      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }, [isOpen, closeOnEscape, setOpen, onEscapeKeyDown]);

    // ============================================
    // GESTIONNAIRES DE CLIC EXTERNE
    // ============================================
    React.useEffect(() => {
      if (!isOpen || !closeOnOutsideClick) return;

      const handleClickOutside = (e: MouseEvent) => {
        const target = e.target as Node;
        const triggerElement = triggerRef.current;
        const contentElement = contentRef.current;

        if (triggerElement?.contains(target) || contentElement?.contains(target)) {
          return;
        }

        setOpen(false);
        onInteractOutside?.(e);
        onPointerDownOutside?.(e);
      };

      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isOpen, closeOnOutsideClick, setOpen, onInteractOutside, onPointerDownOutside]);

    // ============================================
    // CONTEXTE
    // ============================================
    const contextValue = React.useMemo(
      () => ({
        open: isOpen,
        setOpen,
        closeOnSelect,
        triggerRef,
        contentRef,
      }),
      [isOpen, setOpen, closeOnSelect]
    );

    // ============================================
    // POSITIONS
    // ============================================
    const sideStyles = {
      top: 'bottom-full mb-2',
      bottom: 'top-full mt-2',
      left: 'right-full mr-2',
      right: 'left-full ml-2',
    };

    const alignStyles = {
      start: 'left-0',
      center: 'left-1/2 -translate-x-1/2',
      end: 'right-0',
    };

    // ============================================
    // RENDU
    // ============================================
    return (
      <DropdownContext.Provider value={contextValue}>
        <div ref={ref} className={cn('relative inline-block', className)} {...props}>
          {/* Trigger */}
          <div ref={triggerRef} onClick={toggle} className={triggerClassName}>
            {trigger || (
              <Button
                variant="outline"
                className="flex items-center gap-2"
                disabled={disabled}
              >
                <span>Options</span>
                {isOpen ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </Button>
            )}
          </div>

          {/* Content */}
          {isOpen && (
            <div
              ref={contentRef}
              className={cn(
                'absolute z-50 min-w-[8rem] overflow-hidden rounded-md border border-gray-200 bg-white p-1 text-gray-900 shadow-md dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100',
                'data-[state=open]:animate-in data-[state=closed]:animate-out',
                'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
                'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
                sideStyles[side],
                alignStyles[align],
                contentClassName
              )}
              style={{
                ...(sideOffset && { marginTop: side === 'bottom' ? sideOffset : 0 }),
                ...(alignOffset && { marginLeft: align === 'center' ? alignOffset : 0 }),
              }}
            >
              {children}
            </div>
          )}
        </div>
      </DropdownContext.Provider>
    );
  }
);
Dropdown.displayName = 'Dropdown';

// ============================================
// ITEM
// ============================================

const DropdownItem = React.forwardRef<HTMLButtonElement, DropdownItemProps>(
  (
    {
      className,
      inset,
      icon,
      shortcut,
      variant = 'default',
      onSelect,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const { setOpen, closeOnSelect } = useDropdown();

    const variantClasses = {
      default: 'hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-gray-100 focus:bg-gray-100 focus:text-gray-900 dark:focus:bg-gray-800 dark:focus:text-gray-100',
      destructive: 'text-red-600 hover:bg-red-50 hover:text-red-700 dark:text-red-400 dark:hover:bg-red-950/50 dark:hover:text-red-300 focus:bg-red-50 focus:text-red-700 dark:focus:bg-red-950/50 dark:focus:text-red-300',
      success: 'text-green-600 hover:bg-green-50 hover:text-green-700 dark:text-green-400 dark:hover:bg-green-950/50 dark:hover:text-green-300',
      warning: 'text-yellow-600 hover:bg-yellow-50 hover:text-yellow-700 dark:text-yellow-400 dark:hover:bg-yellow-950/50 dark:hover:text-yellow-300',
      info: 'text-blue-600 hover:bg-blue-50 hover:text-blue-700 dark:text-blue-400 dark:hover:bg-blue-950/50 dark:hover:text-blue-300',
    };

    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      if (disabled) return;
      onSelect?.();
      if (closeOnSelect) {
        setOpen(false);
      }
      props.onClick?.(e);
    };

    return (
      <button
        ref={ref}
        className={cn(
          'relative flex w-full cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none',
          'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
          inset && 'pl-8',
          variantClasses[variant],
          className
        )}
        disabled={disabled}
        onClick={handleClick}
        {...props}
      >
        {icon && <span className="mr-2 flex-shrink-0">{icon}</span>}
        <span className="flex-1 text-left">{children}</span>
        {shortcut && (
          <span className="ml-auto text-xs text-gray-400">{shortcut}</span>
        )}
      </button>
    );
  }
);
DropdownItem.displayName = 'DropdownItem';

// ============================================
// GROUP
// ============================================

const DropdownGroup = React.forwardRef<HTMLDivElement, DropdownGroupProps>(
  ({ className, heading, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'overflow-hidden',
        heading && 'border-t border-gray-200 first:border-t-0 dark:border-gray-700',
        className
      )}
      {...props}
    >
      {heading && (
        <div className="px-2 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400">
          {heading}
        </div>
      )}
      <div className="space-y-0.5">{children}</div>
    </div>
  )
);
DropdownGroup.displayName = 'DropdownGroup';

// ============================================
// LABEL
// ============================================

const DropdownLabel = React.forwardRef<HTMLDivElement, DropdownLabelProps>(
  ({ className, inset, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'px-2 py-1.5 text-sm font-semibold text-gray-900 dark:text-gray-100',
        inset && 'pl-8',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
);
DropdownLabel.displayName = 'DropdownLabel';

// ============================================
// SEPARATOR
// ============================================

const DropdownSeparator = React.forwardRef<
  HTMLDivElement,
  DropdownSeparatorProps
>(({ className, ...props }, ref) => (
  <hr
    ref={ref}
    className={cn('-mx-1 my-1 h-px bg-gray-200 dark:bg-gray-700', className)}
    {...props}
  />
));
DropdownSeparator.displayName = 'DropdownSeparator';

// ============================================
// EXPORTATIONS
// ============================================

export {
  Dropdown,
  DropdownItem,
  DropdownGroup,
  DropdownLabel,
  DropdownSeparator,
};

export default Dropdown;

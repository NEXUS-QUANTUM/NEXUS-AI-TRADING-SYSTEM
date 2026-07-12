/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import * as CollapsiblePrimitive from '@radix-ui/react-collapsible';
import { cn } from '@/utils/helpers';
import { ChevronDown, ChevronRight } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface CollapsibleProps
  extends React.ComponentPropsWithoutRef<typeof CollapsiblePrimitive.Root> {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  disabled?: boolean;
  className?: string;
  children?: React.ReactNode;
}

export interface CollapsibleTriggerProps
  extends React.ComponentPropsWithoutRef<typeof CollapsiblePrimitive.Trigger> {
  asChild?: boolean;
  showIcon?: boolean;
  iconPosition?: 'left' | 'right';
  iconClassName?: string;
  children?: React.ReactNode;
}

export interface CollapsibleContentProps
  extends React.ComponentPropsWithoutRef<typeof CollapsiblePrimitive.Content> {
  forceMount?: boolean;
  children?: React.ReactNode;
  className?: string;
}

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

const Collapsible = React.forwardRef<
  React.ElementRef<typeof CollapsiblePrimitive.Root>,
  CollapsibleProps
>(({ className, disabled, children, ...props }, ref) => (
  <CollapsiblePrimitive.Root
    ref={ref}
    className={cn(
      'w-full',
      disabled && 'opacity-50 pointer-events-none cursor-not-allowed',
      className
    )}
    {...props}
  >
    {children}
  </CollapsiblePrimitive.Root>
));
Collapsible.displayName = CollapsiblePrimitive.Root.displayName;

// ============================================
// TRIGGER
// ============================================

const CollapsibleTrigger = React.forwardRef<
  React.ElementRef<typeof CollapsiblePrimitive.Trigger>,
  CollapsibleTriggerProps
>(
  (
    {
      className,
      showIcon = true,
      iconPosition = 'left',
      iconClassName,
      children,
      ...props
    },
    ref
  ) => {
    const context = React.useContext(CollapsiblePrimitive.RootContext);
    const isOpen = context?.open || false;

    return (
      <CollapsiblePrimitive.Trigger
        ref={ref}
        className={cn(
          'flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium',
          'transition-all duration-200 ease-in-out',
          'hover:bg-gray-100 dark:hover:bg-gray-800',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2',
          'disabled:pointer-events-none disabled:opacity-50',
          'data-[state=open]:bg-gray-50 dark:data-[state=open]:bg-gray-800/50',
          className
        )}
        {...props}
      >
        {showIcon && iconPosition === 'left' && (
          <ChevronRight
            className={cn(
              'h-4 w-4 shrink-0 transition-transform duration-200',
              isOpen && 'rotate-90',
              iconClassName
            )}
            aria-hidden="true"
          />
        )}
        {children}
        {showIcon && iconPosition === 'right' && (
          <ChevronDown
            className={cn(
              'ml-auto h-4 w-4 shrink-0 transition-transform duration-200',
              isOpen && 'rotate-180',
              iconClassName
            )}
            aria-hidden="true"
          />
        )}
      </CollapsiblePrimitive.Trigger>
    );
  }
);
CollapsibleTrigger.displayName = CollapsiblePrimitive.Trigger.displayName;

// ============================================
// CONTENT
// ============================================

const CollapsibleContent = React.forwardRef<
  React.ElementRef<typeof CollapsiblePrimitive.Content>,
  CollapsibleContentProps
>(({ className, children, ...props }, ref) => (
  <CollapsiblePrimitive.Content
    ref={ref}
    className={cn(
      'overflow-hidden transition-all duration-300 ease-in-out',
      'data-[state=closed]:animate-collapsible-up',
      'data-[state=open]:animate-collapsible-down',
      className
    )}
    {...props}
  >
    <div className="pb-2 pt-1">{children}</div>
  </CollapsiblePrimitive.Content>
));
CollapsibleContent.displayName = CollapsiblePrimitive.Content.displayName;

// ============================================
// SOUS-COMPOSANTS
// ============================================

export interface CollapsibleItemProps extends CollapsibleProps {
  label: string;
  description?: string;
  icon?: React.ReactNode;
  variant?: 'default' | 'bordered' | 'shadow' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
}

const CollapsibleItem = React.forwardRef<
  React.ElementRef<typeof CollapsiblePrimitive.Root>,
  CollapsibleItemProps
>(
  (
    {
      label,
      description,
      icon,
      variant = 'default',
      size = 'md',
      className,
      children,
      ...props
    },
    ref
  ) => {
    const variantClasses = {
      default: 'border border-gray-200 dark:border-gray-700 rounded-lg',
      bordered: 'border-l-2 border-gray-200 dark:border-gray-700 pl-4',
      shadow: 'shadow-md rounded-lg',
      ghost: 'hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded-lg',
    };

    const sizeClasses = {
      sm: 'text-sm',
      md: 'text-base',
      lg: 'text-lg',
    };

    return (
      <Collapsible
        ref={ref}
        className={cn(
          'overflow-hidden',
          variantClasses[variant],
          sizeClasses[size],
          className
        )}
        {...props}
      >
        <CollapsibleTrigger
          className={cn(
            'flex w-full items-center gap-3 p-3',
            variant === 'ghost' && 'hover:bg-transparent'
          )}
        >
          {icon && <span className="flex-shrink-0">{icon}</span>}
          <div className="flex-1 text-left">
            <div className="font-medium">{label}</div>
            {description && (
              <div className="text-sm text-gray-500 dark:text-gray-400">
                {description}
              </div>
            )}
          </div>
          <ChevronDown
            className={cn(
              'h-4 w-4 shrink-0 text-gray-400 transition-transform duration-200',
              'data-[state=open]:rotate-180'
            )}
          />
        </CollapsibleTrigger>
        <CollapsibleContent className="px-3 pb-3">
          <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
            {children}
          </div>
        </CollapsibleContent>
      </Collapsible>
    );
  }
);
CollapsibleItem.displayName = 'CollapsibleItem';

// ============================================
// EXPORTATIONS
// ============================================

export {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
  CollapsibleItem,
};

export default Collapsible;

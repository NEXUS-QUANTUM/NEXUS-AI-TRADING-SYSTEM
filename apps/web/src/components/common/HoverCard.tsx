/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import * as HoverCardPrimitive from '@radix-ui/react-hover-card';
import { cn } from '@/utils/helpers';

// ============================================
// TYPES
// ============================================

export interface HoverCardProps
  extends React.ComponentPropsWithoutRef<typeof HoverCardPrimitive.Root> {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  openDelay?: number;
  closeDelay?: number;
}

export interface HoverCardTriggerProps
  extends React.ComponentPropsWithoutRef<typeof HoverCardPrimitive.Trigger> {
  asChild?: boolean;
}

export interface HoverCardContentProps
  extends React.ComponentPropsWithoutRef<typeof HoverCardPrimitive.Content> {
  align?: 'start' | 'center' | 'end';
  side?: 'top' | 'bottom' | 'left' | 'right';
  sideOffset?: number;
  alignOffset?: number;
  collisionPadding?: number | { top?: number; right?: number; bottom?: number; left?: number };
  avoidCollisions?: boolean;
  sticky?: 'partial' | 'always';
  hideWhenDetached?: boolean;
  className?: string;
  children?: React.ReactNode;
}

export interface HoverCardPortalProps
  extends React.ComponentPropsWithoutRef<typeof HoverCardPrimitive.Portal> {
  container?: HTMLElement | null;
}

export interface HoverCardArrowProps
  extends React.ComponentPropsWithoutRef<typeof HoverCardPrimitive.Arrow> {
  className?: string;
}

// ============================================
// COMPOSANTS
// ============================================

const HoverCard = HoverCardPrimitive.Root;

const HoverCardTrigger = HoverCardPrimitive.Trigger;

const HoverCardPortal = HoverCardPrimitive.Portal;

const HoverCardArrow = React.forwardRef<
  SVGSVGElement,
  HoverCardArrowProps
>(({ className, ...props }, ref) => (
  <HoverCardPrimitive.Arrow
    ref={ref}
    className={cn('fill-white dark:fill-gray-800', className)}
    {...props}
  />
));
HoverCardArrow.displayName = HoverCardPrimitive.Arrow.displayName;

const HoverCardContent = React.forwardRef<
  React.ElementRef<typeof HoverCardPrimitive.Content>,
  HoverCardContentProps
>(({ className, align = 'center', sideOffset = 4, ...props }, ref) => (
  <HoverCardPrimitive.Portal>
    <HoverCardPrimitive.Content
      ref={ref}
      align={align}
      sideOffset={sideOffset}
      className={cn(
        'z-50 w-64 rounded-md border border-gray-200 bg-white p-4 text-gray-900 shadow-md outline-none dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100',
        'data-[state=open]:animate-in data-[state=closed]:animate-out',
        'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
        'data-[side=bottom]:slide-in-from-top-2',
        'data-[side=left]:slide-in-from-right-2',
        'data-[side=right]:slide-in-from-left-2',
        'data-[side=top]:slide-in-from-bottom-2',
        className
      )}
      {...props}
    />
  </HoverCardPrimitive.Portal>
));
HoverCardContent.displayName = HoverCardPrimitive.Content.displayName;

// ============================================
// SOUS-COMPOSANTS
// ============================================

export interface HoverCardWithTriggerProps extends HoverCardProps {
  trigger: React.ReactNode;
  content: React.ReactNode;
  triggerClassName?: string;
  contentClassName?: string;
  align?: 'start' | 'center' | 'end';
  side?: 'top' | 'bottom' | 'left' | 'right';
  sideOffset?: number;
  alignOffset?: number;
  showArrow?: boolean;
  arrowClassName?: string;
}

const HoverCardWithTrigger = React.forwardRef<
  HTMLDivElement,
  HoverCardWithTriggerProps
>(
  (
    {
      trigger,
      content,
      triggerClassName,
      contentClassName,
      align = 'center',
      side = 'top',
      sideOffset = 4,
      alignOffset = 0,
      showArrow = true,
      arrowClassName,
      ...props
    },
    ref
  ) => {
    return (
      <HoverCard {...props}>
        <HoverCardTrigger asChild>
          <div
            ref={ref}
            className={cn('inline-block cursor-default', triggerClassName)}
          >
            {trigger}
          </div>
        </HoverCardTrigger>
        <HoverCardContent
          align={align}
          side={side}
          sideOffset={sideOffset}
          alignOffset={alignOffset}
          className={contentClassName}
        >
          {showArrow && <HoverCardArrow className={arrowClassName} />}
          {content}
        </HoverCardContent>
      </HoverCard>
    );
  }
);
HoverCardWithTrigger.displayName = 'HoverCardWithTrigger';

// ============================================
// PRÉSÉTS
// ============================================

export interface HoverCardInfoProps extends Omit<HoverCardWithTriggerProps, 'content'> {
  title: string;
  description: string;
  icon?: React.ReactNode;
  footer?: React.ReactNode;
  variant?: 'default' | 'info' | 'success' | 'warning' | 'destructive';
}

const HoverCardInfo = React.forwardRef<HTMLDivElement, HoverCardInfoProps>(
  (
    {
      title,
      description,
      icon,
      footer,
      variant = 'default',
      trigger,
      ...props
    },
    ref
  ) => {
    const variantClasses = {
      default: 'border-gray-200 dark:border-gray-700',
      info: 'border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/20',
      success: 'border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-950/20',
      warning: 'border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-950/20',
      destructive: 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/20',
    };

    return (
      <HoverCardWithTrigger
        ref={ref}
        trigger={trigger}
        content={
          <div className={cn('space-y-2', variantClasses[variant])}>
            <div className="flex items-start gap-3">
              {icon && <div className="flex-shrink-0">{icon}</div>}
              <div className="flex-1">
                <h4 className="font-semibold text-gray-900 dark:text-white">
                  {title}
                </h4>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {description}
                </p>
              </div>
            </div>
            {footer && <div className="border-t border-gray-200 dark:border-gray-700 pt-2">{footer}</div>}
          </div>
        }
        {...props}
      />
    );
  }
);
HoverCardInfo.displayName = 'HoverCardInfo';

// ============================================
// EXPORTATIONS
// ============================================

export {
  HoverCard,
  HoverCardTrigger,
  HoverCardContent,
  HoverCardArrow,
  HoverCardPortal,
  HoverCardWithTrigger,
  HoverCardInfo,
};

export default HoverCard;

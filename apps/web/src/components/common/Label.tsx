/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import * as LabelPrimitive from '@radix-ui/react-label';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/utils/helpers';
import { Info, AlertCircle, CheckCircle, AlertTriangle } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface LabelProps
  extends React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>,
    VariantProps<typeof labelVariants> {
  asChild?: boolean;
  required?: boolean;
  optional?: boolean;
  tooltip?: string;
  tooltipIcon?: React.ReactNode;
  status?: 'default' | 'error' | 'success' | 'warning' | 'info';
  statusMessage?: string;
  htmlFor?: string;
}

// ============================================
// VARIANTS
// ============================================

const labelVariants = cva(
  'text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
  {
    variants: {
      variant: {
        default: 'text-gray-700 dark:text-gray-300',
        error: 'text-red-600 dark:text-red-400',
        success: 'text-green-600 dark:text-green-400',
        warning: 'text-yellow-600 dark:text-yellow-400',
        info: 'text-blue-600 dark:text-blue-400',
        muted: 'text-gray-500 dark:text-gray-400',
        white: 'text-white',
        glass: 'text-white/80',
      },
      size: {
        xs: 'text-[10px]',
        sm: 'text-xs',
        md: 'text-sm',
        lg: 'text-base',
        xl: 'text-lg',
      },
      weight: {
        normal: 'font-normal',
        medium: 'font-medium',
        semibold: 'font-semibold',
        bold: 'font-bold',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
      weight: 'medium',
    },
  }
);

// ============================================
// COMPOSANT
// ============================================

const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  LabelProps
>(
  (
    {
      className,
      variant,
      size,
      weight,
      asChild,
      required = false,
      optional = false,
      tooltip,
      tooltipIcon,
      status,
      statusMessage,
      children,
      ...props
    },
    ref
  ) => {
    // ============================================
    // ÉTATS
    // ============================================
    const [isTooltipVisible, setIsTooltipVisible] = React.useState(false);

    // ============================================
    // STATUS ICONS
    // ============================================
    const statusIcons = {
      error: AlertCircle,
      success: CheckCircle,
      warning: AlertTriangle,
      info: Info,
      default: null,
    };

    const StatusIcon = status ? statusIcons[status] : null;
    const actualVariant = status || variant || 'default';

    // ============================================
    // RENDU
    // ============================================

    const Comp = asChild ? 'span' : LabelPrimitive.Root;

    return (
      <div className="inline-flex items-center gap-1.5">
        <Comp
          ref={ref}
          className={cn(
            labelVariants({ variant: actualVariant, size, weight }),
            className
          )}
          {...props}
        >
          {children}
          {required && (
            <span
              className={cn(
                'ml-0.5 text-red-500',
                actualVariant === 'error' && 'text-red-600'
              )}
              aria-hidden="true"
            >
              *
            </span>
          )}
          {optional && (
            <span
              className={cn(
                'ml-1 text-xs text-gray-400 dark:text-gray-500',
                actualVariant === 'error' && 'text-red-400'
              )}
            >
              (optionnel)
            </span>
          )}
        </Comp>

        {/* Tooltip */}
        {tooltip && (
          <div
            className="relative inline-flex"
            onMouseEnter={() => setIsTooltipVisible(true)}
            onMouseLeave={() => setIsTooltipVisible(false)}
          >
            <span className="cursor-help text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300">
              {tooltipIcon || <Info className="h-4 w-4" />}
            </span>
            {isTooltipVisible && (
              <div
                className={cn(
                  'absolute z-50 min-w-[200px] max-w-xs rounded-md',
                  'bg-gray-900 px-3 py-2 text-sm text-white shadow-lg',
                  'animate-in fade-in-0 zoom-in-95',
                  'bottom-full left-1/2 -translate-x-1/2 mb-2'
                )}
              >
                {tooltip}
                <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
              </div>
            )}
          </div>
        )}

        {/* Status icon */}
        {StatusIcon && (
          <span className="flex-shrink-0">
            <StatusIcon
              className={cn(
                'h-4 w-4',
                status === 'error' && 'text-red-500',
                status === 'success' && 'text-green-500',
                status === 'warning' && 'text-yellow-500',
                status === 'info' && 'text-blue-500'
              )}
            />
          </span>
        )}

        {/* Status message */}
        {statusMessage && (
          <span
            className={cn(
              'text-xs',
              status === 'error' && 'text-red-500',
              status === 'success' && 'text-green-500',
              status === 'warning' && 'text-yellow-500',
              status === 'info' && 'text-blue-500'
            )}
          >
            {statusMessage}
          </span>
        )}
      </div>
    );
  }
);
Label.displayName = LabelPrimitive.Root.displayName;

// ============================================
// SOUS-COMPOSANTS
// ============================================

export interface LabelGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  orientation?: 'horizontal' | 'vertical';
  spacing?: 'sm' | 'md' | 'lg';
}

const LabelGroup = React.forwardRef<HTMLDivElement, LabelGroupProps>(
  ({ className, orientation = 'horizontal', spacing = 'md', children, ...props }, ref) => {
    const spacingClasses = {
      horizontal: {
        sm: 'gap-2',
        md: 'gap-3',
        lg: 'gap-4',
      },
      vertical: {
        sm: 'space-y-1',
        md: 'space-y-2',
        lg: 'space-y-3',
      },
    };

    return (
      <div
        ref={ref}
        className={cn(
          'flex',
          orientation === 'horizontal' ? 'flex-row flex-wrap items-center' : 'flex-col',
          spacingClasses[orientation][spacing],
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }
);
LabelGroup.displayName = 'LabelGroup';

// ============================================
// EXPORTATIONS
// ============================================

export { Label, LabelGroup, labelVariants };

export default Label;

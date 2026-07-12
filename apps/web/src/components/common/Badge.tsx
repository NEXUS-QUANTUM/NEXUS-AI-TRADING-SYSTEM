/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/utils/helpers';
import { X } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {
  asChild?: boolean;
  closable?: boolean;
  onClose?: () => void;
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
  pulse?: boolean;
  animated?: boolean;
}

// ============================================
// VARIANTS
// ============================================

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200',
        primary:
          'border-transparent bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
        secondary:
          'border-transparent bg-gray-200 text-gray-900 dark:bg-gray-700 dark:text-gray-200',
        success:
          'border-transparent bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
        warning:
          'border-transparent bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
        danger:
          'border-transparent bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
        info:
          'border-transparent bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-400',
        outline:
          'border-gray-300 text-gray-800 dark:border-gray-600 dark:text-gray-200',
        gradient:
          'border-transparent bg-gradient-to-r from-blue-500 to-purple-500 text-white',
        glass:
          'border border-white/20 bg-white/10 backdrop-blur-sm text-white',
        subtle:
          'border-transparent bg-gray-50 text-gray-600 dark:bg-gray-800/50 dark:text-gray-400',
        destructive:
          'border-transparent bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
      },
      size: {
        sm: 'px-2 py-0.5 text-[10px]',
        md: 'px-2.5 py-0.5 text-xs',
        lg: 'px-3 py-1 text-sm',
      },
      rounded: {
        none: 'rounded-none',
        sm: 'rounded-sm',
        md: 'rounded-md',
        lg: 'rounded-lg',
        full: 'rounded-full',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
      rounded: 'full',
    },
  }
);

// ============================================
// COMPOSANT
// ============================================

const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  (
    {
      className,
      variant,
      size,
      rounded,
      asChild,
      closable = false,
      onClose,
      icon,
      iconPosition = 'left',
      pulse = false,
      animated = false,
      children,
      ...props
    },
    ref
  ) => {
    const [isVisible, setIsVisible] = React.useState(true);

    const handleClose = (e: React.MouseEvent) => {
      e.stopPropagation();
      setIsVisible(false);
      onClose?.();
    };

    if (!isVisible) return null;

    const Comp = asChild ? 'span' : 'div';

    return (
      <Comp
        ref={ref}
        className={cn(
          badgeVariants({ variant, size, rounded }),
          'relative',
          animated && 'transition-all duration-200 hover:scale-105',
          pulse && 'animate-pulse',
          closable && 'pr-6',
          className
        )}
        {...props}
      >
        {/* Icône gauche */}
        {icon && iconPosition === 'left' && (
          <span className="mr-1">{icon}</span>
        )}
        
        {children}
        
        {/* Icône droite */}
        {icon && iconPosition === 'right' && (
          <span className="ml-1">{icon}</span>
        )}

        {/* Bouton de fermeture */}
        {closable && (
          <button
            onClick={handleClose}
            className={cn(
              'ml-1 rounded-full p-0.5 transition-colors hover:bg-black/10 dark:hover:bg-white/10',
              'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2'
            )}
            aria-label="Fermer"
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </Comp>
    );
  }
);
Badge.displayName = 'Badge';

// ============================================
// SOUS-COMPOSANTS
// ============================================

export interface BadgeDotProps extends Omit<BadgeProps, 'variant'> {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  dotColor?: string;
  size?: 'sm' | 'md' | 'lg';
}

const BadgeDot = React.forwardRef<HTMLDivElement, BadgeDotProps>(
  ({ className, variant = 'default', dotColor, size = 'md', children, ...props }, ref) => {
    const dotColors = {
      default: 'bg-gray-500',
      success: 'bg-green-500',
      warning: 'bg-yellow-500',
      danger: 'bg-red-500',
      info: 'bg-blue-500',
    };

    const dotSizes = {
      sm: 'h-1.5 w-1.5',
      md: 'h-2 w-2',
      lg: 'h-2.5 w-2.5',
    };

    return (
      <Badge
        ref={ref}
        variant="subtle"
        className={cn('gap-1.5', className)}
        {...props}
      >
        <span
          className={cn(
            'inline-block rounded-full',
            dotColors[variant],
            dotSizes[size],
            dotColor
          )}
          aria-hidden="true"
        />
        {children}
      </Badge>
    );
  }
);
BadgeDot.displayName = 'BadgeDot';

export interface BadgeCountProps extends Omit<BadgeProps, 'variant'> {
  count: number;
  max?: number;
  showZero?: boolean;
}

const BadgeCount = React.forwardRef<HTMLDivElement, BadgeCountProps>(
  ({ count, max = 99, showZero = false, className, ...props }, ref) => {
    if (!showZero && count === 0) return null;

    const display = count > max ? `${max}+` : String(count);

    return (
      <Badge
        ref={ref}
        variant="danger"
        className={cn('px-1.5 py-0.5 text-[10px] font-bold', className)}
        {...props}
      >
        {display}
      </Badge>
    );
  }
);
BadgeCount.displayName = 'BadgeCount';

export interface BadgeStatusProps extends Omit<BadgeProps, 'variant'> {
  status: 'online' | 'offline' | 'away' | 'busy';
  label?: string;
}

const BadgeStatus = React.forwardRef<HTMLDivElement, BadgeStatusProps>(
  ({ status, label, className, ...props }, ref) => {
    const statusConfig = {
      online: { color: 'bg-green-500', label: 'En ligne' },
      offline: { color: 'bg-gray-400', label: 'Hors ligne' },
      away: { color: 'bg-yellow-500', label: 'Absent' },
      busy: { color: 'bg-red-500', label: 'Occupé' },
    };

    const config = statusConfig[status];

    return (
      <Badge
        ref={ref}
        variant="subtle"
        className={cn('gap-1.5', className)}
        {...props}
      >
        <span
          className={cn(
            'inline-block h-2 w-2 rounded-full',
            config.color,
            status === 'online' && 'animate-pulse'
          )}
          aria-hidden="true"
        />
        <span className="text-xs">{label || config.label}</span>
      </Badge>
    );
  }
);
BadgeStatus.displayName = 'BadgeStatus';

// ============================================
// EXPORTATIONS
// ============================================

export {
  Badge,
  BadgeDot,
  BadgeCount,
  BadgeStatus,
  badgeVariants,
};

export default Badge;

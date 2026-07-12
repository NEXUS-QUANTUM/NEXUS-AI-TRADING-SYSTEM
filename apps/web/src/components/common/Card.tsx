/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/utils/helpers';

// ============================================
// TYPES
// ============================================

export interface CardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {
  asChild?: boolean;
  hoverable?: boolean;
  clickable?: boolean;
  onClick?: () => void;
}

export interface CardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  asChild?: boolean;
}

export interface CardFooterProps extends React.HTMLAttributes<HTMLDivElement> {
  asChild?: boolean;
}

export interface CardTitleProps extends React.HTMLAttributes<HTMLHeadingElement> {
  asChild?: boolean;
}

export interface CardDescriptionProps extends React.HTMLAttributes<HTMLParagraphElement> {
  asChild?: boolean;
}

export interface CardContentProps extends React.HTMLAttributes<HTMLDivElement> {
  asChild?: boolean;
}

// ============================================
// VARIANTS
// ============================================

const cardVariants = cva(
  'rounded-lg border bg-white text-gray-900 shadow-sm dark:bg-gray-900 dark:text-gray-100',
  {
    variants: {
      variant: {
        default: 'border-gray-200 dark:border-gray-800',
        elevated: 'border-transparent shadow-md hover:shadow-lg dark:shadow-gray-800/30',
        outline: 'border-2 border-gray-200 dark:border-gray-700',
        ghost: 'border-transparent shadow-none bg-transparent dark:bg-transparent',
        glass: 'border border-white/20 bg-white/10 backdrop-blur-sm dark:bg-gray-900/50',
        gradient: 'border-transparent bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-950/30 dark:to-purple-950/30',
        destructive: 'border-red-200 bg-red-50 dark:border-red-900/30 dark:bg-red-950/20',
        success: 'border-green-200 bg-green-50 dark:border-green-900/30 dark:bg-green-950/20',
        warning: 'border-yellow-200 bg-yellow-50 dark:border-yellow-900/30 dark:bg-yellow-950/20',
        info: 'border-blue-200 bg-blue-50 dark:border-blue-900/30 dark:bg-blue-950/20',
      },
      padding: {
        none: 'p-0',
        sm: 'p-3',
        md: 'p-4',
        lg: 'p-6',
        xl: 'p-8',
      },
      rounded: {
        none: 'rounded-none',
        sm: 'rounded-sm',
        md: 'rounded-md',
        lg: 'rounded-lg',
        xl: 'rounded-xl',
        '2xl': 'rounded-2xl',
        full: 'rounded-full',
      },
    },
    defaultVariants: {
      variant: 'default',
      padding: 'md',
      rounded: 'lg',
    },
  }
);

// ============================================
// COMPOSANTS
// ============================================

const Card = React.forwardRef<HTMLDivElement, CardProps>(
  (
    {
      className,
      variant,
      padding,
      rounded,
      hoverable = false,
      clickable = false,
      onClick,
      children,
      ...props
    },
    ref
  ) => {
    const Comp = onClick ? 'button' : 'div';

    return (
      <Comp
        ref={ref as any}
        className={cn(
          cardVariants({ variant, padding, rounded, className }),
          hoverable && 'transition-all duration-200 hover:shadow-md hover:scale-[1.01]',
          clickable && 'cursor-pointer transition-all duration-200 hover:shadow-md active:scale-[0.98]',
          onClick && 'text-left'
        )}
        onClick={onClick}
        {...props}
      >
        {children}
      </Comp>
    );
  }
);
Card.displayName = 'Card';

const CardHeader = React.forwardRef<HTMLDivElement, CardHeaderProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('flex flex-col space-y-1.5', className)}
      {...props}
    />
  )
);
CardHeader.displayName = 'CardHeader';

const CardTitle = React.forwardRef<HTMLHeadingElement, CardTitleProps>(
  ({ className, ...props }, ref) => (
    <h3
      ref={ref}
      className={cn(
        'text-2xl font-semibold leading-none tracking-tight',
        'text-gray-900 dark:text-white',
        className
      )}
      {...props}
    />
  )
);
CardTitle.displayName = 'CardTitle';

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  CardDescriptionProps
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn(
      'text-sm text-gray-500 dark:text-gray-400',
      className
    )}
    {...props}
  />
));
CardDescription.displayName = 'CardDescription';

const CardContent = React.forwardRef<HTMLDivElement, CardContentProps>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('', className)} {...props} />
  )
);
CardContent.displayName = 'CardContent';

const CardFooter = React.forwardRef<HTMLDivElement, CardFooterProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex items-center border-t border-gray-200 pt-4 dark:border-gray-800',
        className
      )}
      {...props}
    />
  )
);
CardFooter.displayName = 'CardFooter';

// ============================================
// SOUS-COMPOSANTS
// ============================================

export interface CardGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  columns?: 1 | 2 | 3 | 4;
  gap?: 'sm' | 'md' | 'lg';
}

const CardGroup = React.forwardRef<HTMLDivElement, CardGroupProps>(
  ({ className, columns = 3, gap = 'md', children, ...props }, ref) => {
    const columnsClasses = {
      1: 'grid-cols-1',
      2: 'grid-cols-1 sm:grid-cols-2',
      3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
      4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
    };

    const gapClasses = {
      sm: 'gap-3',
      md: 'gap-4',
      lg: 'gap-6',
    };

    return (
      <div
        ref={ref}
        className={cn(
          'grid',
          columnsClasses[columns],
          gapClasses[gap],
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }
);
CardGroup.displayName = 'CardGroup';

export interface CardWithIconProps extends CardProps {
  icon: React.ReactNode;
  iconPosition?: 'top' | 'left' | 'right';
  iconClassName?: string;
}

const CardWithIcon = React.forwardRef<HTMLDivElement, CardWithIconProps>(
  (
    {
      icon,
      iconPosition = 'top',
      iconClassName,
      children,
      className,
      ...props
    },
    ref
  ) => {
    const flexClasses = {
      top: 'flex-col',
      left: 'flex-row',
      right: 'flex-row-reverse',
    };

    return (
      <Card
        ref={ref}
        className={cn(
          'flex',
          flexClasses[iconPosition],
          iconPosition !== 'top' && 'items-center gap-4',
          className
        )}
        {...props}
      >
        <div
          className={cn(
            'flex-shrink-0',
            iconPosition === 'top' && 'mb-4',
            iconClassName
          )}
        >
          {icon}
        </div>
        <div className="flex-1">{children}</div>
      </Card>
    );
  }
);
CardWithIcon.displayName = 'CardWithIcon';

// ============================================
// EXPORTATIONS
// ============================================

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardDescription,
  CardContent,
  CardGroup,
  CardWithIcon,
  cardVariants,
};

export default Card;

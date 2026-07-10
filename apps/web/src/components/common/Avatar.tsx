/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import * as AvatarPrimitive from '@radix-ui/react-avatar';
import { cn } from '@/utils/helpers';
import { User, Loader2 } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface AvatarProps
  extends React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Root> {
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl';
  status?: 'online' | 'offline' | 'away' | 'busy' | 'none';
  statusPosition?: 'top-right' | 'bottom-right' | 'bottom-left' | 'top-left';
  ring?: boolean;
  ringColor?: string;
  isLoading?: boolean;
}

export interface AvatarImageProps
  extends React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Image> {
  fallbackDelay?: number;
}

export interface AvatarFallbackProps
  extends React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Fallback> {
  delayMs?: number;
}

// ============================================
// CONSTANTES
// ============================================

const SIZE_MAP = {
  xs: 'h-6 w-6 text-xs',
  sm: 'h-8 w-8 text-sm',
  md: 'h-10 w-10 text-base',
  lg: 'h-12 w-12 text-lg',
  xl: 'h-16 w-16 text-xl',
  '2xl': 'h-24 w-24 text-2xl',
};

const STATUS_SIZE_MAP = {
  xs: 'h-1.5 w-1.5',
  sm: 'h-2 w-2',
  md: 'h-2.5 w-2.5',
  lg: 'h-3 w-3',
  xl: 'h-4 w-4',
  '2xl': 'h-5 w-5',
};

const STATUS_COLORS = {
  online: 'bg-green-500',
  offline: 'bg-gray-400',
  away: 'bg-yellow-500',
  busy: 'bg-red-500',
  none: '',
};

const STATUS_POSITIONS = {
  'top-right': '-top-0.5 -right-0.5',
  'bottom-right': '-bottom-0.5 -right-0.5',
  'bottom-left': '-bottom-0.5 -left-0.5',
  'top-left': '-top-0.5 -left-0.5',
};

// ============================================
// COMPOSANTS
// ============================================

const Avatar = React.forwardRef<
  React.ElementRef<typeof AvatarPrimitive.Root>,
  AvatarProps
>(
  (
    {
      className,
      size = 'md',
      status = 'none',
      statusPosition = 'bottom-right',
      ring = false,
      ringColor = 'ring-2 ring-white dark:ring-gray-900',
      isLoading = false,
      children,
      ...props
    },
    ref
  ) => {
    const sizeClass = SIZE_MAP[size];
    const statusSize = STATUS_SIZE_MAP[size];
    const statusColor = STATUS_COLORS[status];
    const statusPositionClass = STATUS_POSITIONS[statusPosition];

    return (
      <div className="relative inline-block">
        <AvatarPrimitive.Root
          ref={ref}
          className={cn(
            'relative flex shrink-0 overflow-hidden rounded-full',
            sizeClass,
            ring && ringColor,
            className
          )}
          {...props}
        >
          {isLoading ? (
            <div className="flex h-full w-full items-center justify-center bg-gray-200 dark:bg-gray-700">
              <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
            </div>
          ) : (
            children
          )}
        </AvatarPrimitive.Root>

        {/* Statut */}
        {status !== 'none' && (
          <span
            className={cn(
              'absolute block rounded-full border-2 border-white dark:border-gray-900',
              statusSize,
              statusColor,
              statusPositionClass
            )}
            aria-label={`Statut: ${status}`}
          />
        )}

        {/* Animation de pulsation pour le statut "en ligne" */}
        {status === 'online' && (
          <span
            className={cn(
              'absolute block rounded-full border-2 border-white dark:border-gray-900',
              statusSize,
              statusColor,
              statusPositionClass,
              'animate-ping'
            )}
            style={{ animationDuration: '2s' }}
          />
        )}
      </div>
    );
  }
);
Avatar.displayName = AvatarPrimitive.Root.displayName;

const AvatarImage = React.forwardRef<
  React.ElementRef<typeof AvatarPrimitive.Image>,
  AvatarImageProps
>(({ className, fallbackDelay = 500, ...props }, ref) => (
  <AvatarPrimitive.Image
    ref={ref}
    className={cn('aspect-square h-full w-full object-cover', className)}
    style={{ transition: 'opacity 0.3s ease' }}
    {...props}
  />
));
AvatarImage.displayName = AvatarPrimitive.Image.displayName;

const AvatarFallback = React.forwardRef<
  React.ElementRef<typeof AvatarPrimitive.Fallback>,
  AvatarFallbackProps
>(({ className, delayMs = 0, ...props }, ref) => (
  <AvatarPrimitive.Fallback
    ref={ref}
    className={cn(
      'flex h-full w-full items-center justify-center rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 font-medium',
      className
    )}
    style={{ transition: 'opacity 0.3s ease' }}
    {...props}
  />
));
AvatarFallback.displayName = AvatarPrimitive.Fallback.displayName;

// ============================================
// COMPOSANTS UTILITAIRES
// ============================================

export interface AvatarWithFallbackProps extends AvatarProps {
  src?: string;
  alt?: string;
  fallback?: string;
  fallbackIcon?: React.ReactNode;
}

const AvatarWithFallback = React.forwardRef<
  React.ElementRef<typeof AvatarPrimitive.Root>,
  AvatarWithFallbackProps
>(
  (
    {
      src,
      alt = 'Avatar',
      fallback,
      fallbackIcon = <User className="h-1/2 w-1/2" />,
      className,
      ...props
    },
    ref
  ) => {
    return (
      <Avatar ref={ref} className={className} {...props}>
        <AvatarImage src={src} alt={alt} />
        <AvatarFallback delayMs={300}>
          {fallback ? (
            <span className="text-sm font-medium">{fallback}</span>
          ) : (
            fallbackIcon
          )}
        </AvatarFallback>
      </Avatar>
    );
  }
);
AvatarWithFallback.displayName = 'AvatarWithFallback';

// ============================================
// EXPORTATIONS
// ============================================

export {
  Avatar,
  AvatarImage,
  AvatarFallback,
  AvatarWithFallback,
};

export default Avatar;

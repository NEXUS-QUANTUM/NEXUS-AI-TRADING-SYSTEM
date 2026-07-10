/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import { cn } from '@/utils/helpers';
import { Avatar, AvatarImage, AvatarFallback, type AvatarProps } from './Avatar';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './Tooltip';

// ============================================
// TYPES
// ============================================

export interface AvatarGroupItem {
  id: string;
  src?: string;
  alt?: string;
  fallback: string;
  name?: string;
  status?: 'online' | 'offline' | 'away' | 'busy' | 'none';
  tooltip?: string;
}

export interface AvatarGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  items: AvatarGroupItem[];
  max?: number;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl';
  spacing?: 'sm' | 'md' | 'lg';
  showTooltip?: boolean;
  showStatus?: boolean;
  showCount?: boolean;
  countLabel?: string;
  onClickItem?: (item: AvatarGroupItem) => void;
  ring?: boolean;
  ringColor?: string;
  className?: string;
}

// ============================================
// CONSTANTES
// ============================================

const SPACING_MAP = {
  sm: '-space-x-1',
  md: '-space-x-2',
  lg: '-space-x-3',
};

const AVATAR_SIZE_MAP = {
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

// ============================================
// COMPOSANT
// ============================================

const AvatarGroup = React.forwardRef<HTMLDivElement, AvatarGroupProps>(
  (
    {
      items,
      max = 5,
      size = 'md',
      spacing = 'md',
      showTooltip = true,
      showStatus = true,
      showCount = true,
      countLabel = '+{count}',
      onClickItem,
      ring = false,
      ringColor = 'ring-2 ring-white dark:ring-gray-900',
      className,
      ...props
    },
    ref
  ) => {
    const visibleItems = items.slice(0, max);
    const hiddenCount = items.length - max;
    const sizeClass = AVATAR_SIZE_MAP[size];
    const spacingClass = SPACING_MAP[spacing];
    const statusSize = STATUS_SIZE_MAP[size];

    return (
      <div
        ref={ref}
        className={cn(
          'flex flex-wrap items-center',
          spacingClass,
          className
        )}
        {...props}
      >
        <TooltipProvider delayDuration={200}>
          {visibleItems.map((item, index) => {
            const avatarContent = (
              <Avatar
                key={item.id}
                size={size}
                status={showStatus ? item.status || 'none' : 'none'}
                ring={ring}
                ringColor={ringColor}
                className={cn(
                  'cursor-pointer transition-transform hover:scale-105 hover:z-10',
                  index === 0 && 'relative z-10',
                  index > 0 && `relative z-${10 - index}`
                )}
                onClick={() => onClickItem?.(item)}
              >
                <AvatarImage src={item.src} alt={item.alt || item.name || item.fallback} />
                <AvatarFallback>{item.fallback}</AvatarFallback>
              </Avatar>
            );

            if (showTooltip && item.tooltip) {
              return (
                <Tooltip key={item.id}>
                  <TooltipTrigger asChild>
                    {avatarContent}
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{item.tooltip}</p>
                  </TooltipContent>
                </Tooltip>
              );
            }

            return avatarContent;
          })}

          {/* Compteur d'avatars supplémentaires */}
          {showCount && hiddenCount > 0 && (
            <Avatar
              size={size}
              ring={ring}
              ringColor={ringColor}
              className="relative z-0 cursor-default"
            >
              <AvatarFallback className="bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
                {countLabel.replace('{count}', String(hiddenCount))}
              </AvatarFallback>
            </Avatar>
          )}
        </TooltipProvider>
      </div>
    );
  }
);
AvatarGroup.displayName = 'AvatarGroup';

// ============================================
// SOUS-COMPOSANTS
// ============================================

export interface AvatarGroupWithStackProps extends AvatarGroupProps {
  stackDirection?: 'row' | 'column';
}

const AvatarGroupWithStack = React.forwardRef<
  HTMLDivElement,
  AvatarGroupWithStackProps
>(
  (
    {
      items,
      max = 5,
      size = 'md',
      spacing = 'md',
      stackDirection = 'row',
      className,
      ...props
    },
    ref
  ) => {
    return (
      <AvatarGroup
        ref={ref}
        items={items}
        max={max}
        size={size}
        spacing={spacing}
        className={cn(
          stackDirection === 'column' && 'flex-col',
          className
        )}
        {...props}
      />
    );
  }
);
AvatarGroupWithStack.displayName = 'AvatarGroupWithStack';

// ============================================
// EXPORTATIONS
// ============================================

export { AvatarGroup, AvatarGroupWithStack };

export default AvatarGroup;

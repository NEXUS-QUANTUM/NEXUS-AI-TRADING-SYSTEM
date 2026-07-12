/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import { cn } from '@/utils/helpers';
import NextLink from 'next/link';
import { cva, type VariantProps } from 'class-variance-authority';
import { ExternalLink, ChevronRight, ChevronLeft, Loader2 } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface LinkProps
  extends React.AnchorHTMLAttributes<HTMLAnchorElement>,
    VariantProps<typeof linkVariants> {
  asChild?: boolean;
  href: string;
  external?: boolean;
  isLoading?: boolean;
  loadingText?: string;
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
  underline?: boolean;
  underlineOffset?: 'none' | 'sm' | 'md' | 'lg';
  target?: '_blank' | '_self' | '_parent' | '_top';
  rel?: string;
  prefetch?: boolean;
  scroll?: boolean;
  shallow?: boolean;
  replace?: boolean;
  locale?: string;
  onNavigate?: () => void;
  activeClassName?: string;
  exact?: boolean;
}

// ============================================
// VARIANTS
// ============================================

const linkVariants = cva(
  'inline-flex items-center gap-1.5 transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300',
        primary: 'text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300',
        secondary: 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200',
        muted: 'text-gray-500 hover:text-gray-700 dark:text-gray-500 dark:hover:text-gray-300',
        white: 'text-white hover:text-white/80',
        destructive: 'text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300',
        success: 'text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-300',
        warning: 'text-yellow-600 hover:text-yellow-800 dark:text-yellow-400 dark:hover:text-yellow-300',
        info: 'text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300',
        glass: 'text-white/80 hover:text-white backdrop-blur-sm bg-white/10 px-3 py-1.5 rounded-lg',
        gradient: 'bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent hover:from-blue-700 hover:to-purple-700',
      },
      size: {
        xs: 'text-xs',
        sm: 'text-sm',
        md: 'text-base',
        lg: 'text-lg',
        xl: 'text-xl',
      },
      weight: {
        normal: 'font-normal',
        medium: 'font-medium',
        semibold: 'font-semibold',
        bold: 'font-bold',
      },
      underline: {
        none: 'no-underline',
        hover: 'hover:underline',
        always: 'underline underline-offset-2',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
      weight: 'medium',
      underline: 'hover',
    },
  }
);

// ============================================
// COMPOSANT
// ============================================

const Link = React.forwardRef<HTMLAnchorElement, LinkProps>(
  (
    {
      className,
      href,
      variant,
      size,
      weight,
      underline,
      external = false,
      isLoading = false,
      loadingText,
      icon,
      iconPosition = 'left',
      underlineOffset = 'md',
      target,
      rel,
      prefetch = true,
      scroll = true,
      shallow = false,
      replace = false,
      locale,
      onNavigate,
      activeClassName,
      exact = false,
      children,
      ...props
    },
    ref
  ) => {
    // ============================================
    // RÉFÉRENCES
    // ============================================
    const linkRef = React.useRef<HTMLAnchorElement>(null);
    const [isActive, setIsActive] = React.useState(false);

    // ============================================
    // EFFETS
    // ============================================
    React.useEffect(() => {
      if (typeof window === 'undefined' || !activeClassName) return;

      const checkActive = () => {
        const currentPath = window.location.pathname;
        const linkPath = href.split('?')[0];
        const isActivePath = exact
          ? currentPath === linkPath
          : currentPath.startsWith(linkPath);
        setIsActive(isActivePath);
      };

      checkActive();
      window.addEventListener('popstate', checkActive);
      return () => window.removeEventListener('popstate', checkActive);
    }, [href, activeClassName, exact]);

    // ============================================
    // GESTIONNAIRES
    // ============================================

    const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
      if (isLoading) {
        e.preventDefault();
        return;
      }

      onNavigate?.();
      props.onClick?.(e);
    };

    // ============================================
    // PROPS
    // ============================================

    const linkProps = {
      ref: ref || linkRef,
      href,
      target: external ? '_blank' : target,
      rel: external ? 'noopener noreferrer' : rel,
      prefetch,
      scroll,
      shallow,
      replace,
      locale,
      className: cn(
        linkVariants({ variant, size, weight, underline }),
        'relative',
        isActive && activeClassName,
        className
      ),
      onClick: handleClick,
      ...props,
    };

    // ============================================
    // RENDU
    // ============================================

    // Si c'est un lien externe et non Next.js
    if (external || href.startsWith('http') || href.startsWith('mailto:')) {
      return (
        <a
          {...linkProps}
          target={target || '_blank'}
          rel={rel || 'noopener noreferrer'}
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              {loadingText || children}
            </>
          ) : (
            <>
              {icon && iconPosition === 'left' && (
                <span className="flex-shrink-0">{icon}</span>
              )}
              {children}
              {icon && iconPosition === 'right' && (
                <span className="flex-shrink-0">{icon}</span>
              )}
              {external && (
                <ExternalLink className="ml-0.5 h-3.5 w-3.5 flex-shrink-0" />
              )}
            </>
          )}
        </a>
      );
    }

    // Lien Next.js
    return (
      <NextLink {...linkProps}>
        {isLoading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            {loadingText || children}
          </>
        ) : (
          <>
            {icon && iconPosition === 'left' && (
              <span className="flex-shrink-0">{icon}</span>
            )}
            {children}
            {icon && iconPosition === 'right' && (
              <span className="flex-shrink-0">{icon}</span>
            )}
          </>
        )}
      </NextLink>
    );
  }
);
Link.displayName = 'Link';

// ============================================
// SOUS-COMPOSANTS
// ============================================

export interface LinkGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  orientation?: 'horizontal' | 'vertical';
  spacing?: 'sm' | 'md' | 'lg';
}

const LinkGroup = React.forwardRef<HTMLDivElement, LinkGroupProps>(
  ({ className, orientation = 'horizontal', spacing = 'md', children, ...props }, ref) => {
    const spacingClasses = {
      horizontal: {
        sm: 'gap-2',
        md: 'gap-4',
        lg: 'gap-6',
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
LinkGroup.displayName = 'LinkGroup';

export interface LinkIconProps extends React.HTMLAttributes<HTMLSpanElement> {
  asChild?: boolean;
}

const LinkIcon = React.forwardRef<HTMLSpanElement, LinkIconProps>(
  ({ className, children, ...props }, ref) => (
    <span
      ref={ref}
      className={cn('flex-shrink-0', className)}
      {...props}
    >
      {children}
    </span>
  )
);
LinkIcon.displayName = 'LinkIcon';

// ============================================
// EXPORTATIONS
// ============================================

export { Link, LinkGroup, LinkIcon, linkVariants };

export default Link;

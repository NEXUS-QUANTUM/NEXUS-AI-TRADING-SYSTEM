/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import { cn } from '@/utils/helpers';
import { ChevronRight, Home, Slash } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

// ============================================
// TYPES
// ============================================

export interface BreadcrumbProps extends React.HTMLAttributes<HTMLElement> {
  separator?: React.ReactNode;
  showHome?: boolean;
  homeLabel?: string;
  homeIcon?: React.ReactNode;
  capitalize?: boolean;
  maxItems?: number;
  collapseLabel?: string;
  onItemClick?: (item: BreadcrumbItem) => void;
  items?: BreadcrumbItem[];
}

export interface BreadcrumbItem {
  label: string;
  href?: string;
  icon?: React.ReactNode;
  active?: boolean;
}

export interface BreadcrumbListProps extends React.HTMLAttributes<HTMLOListElement> {}

export interface BreadcrumbItemProps extends React.HTMLAttributes<HTMLLIElement> {
  href?: string;
  isCurrent?: boolean;
  icon?: React.ReactNode;
}

export interface BreadcrumbLinkProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  asChild?: boolean;
  href: string;
}

export interface BreadcrumbPageProps extends React.HTMLAttributes<HTMLSpanElement> {}

export interface BreadcrumbSeparatorProps extends React.HTMLAttributes<HTMLSpanElement> {}

// ============================================
// COMPOSANTS
// ============================================

const Breadcrumb = React.forwardRef<HTMLElement, BreadcrumbProps>(
  (
    {
      className,
      separator = <ChevronRight className="h-4 w-4" />,
      showHome = true,
      homeLabel = 'Accueil',
      homeIcon = <Home className="h-4 w-4" />,
      capitalize = true,
      maxItems = 0,
      collapseLabel = '...',
      onItemClick,
      items: propItems,
      children,
      ...props
    },
    ref
  ) => {
    const pathname = usePathname();

    // Générer les items à partir du pathname si non fournis
    const generateItems = (): BreadcrumbItem[] => {
      if (propItems) return propItems;

      const paths = pathname.split('/').filter(Boolean);
      const items: BreadcrumbItem[] = [];

      if (showHome) {
        items.push({
          label: homeLabel,
          href: '/',
          icon: homeIcon,
        });
      }

      let currentPath = '';
      paths.forEach((path, index) => {
        currentPath += `/${path}`;
        const isLast = index === paths.length - 1;
        items.push({
          label: decodeURIComponent(path.replace(/-/g, ' ')),
          href: isLast ? undefined : currentPath,
          active: isLast,
        });
      });

      return items;
    };

    const items = generateItems();

    // Appliquer la limite d'items
    let displayItems = items;
    let hiddenCount = 0;

    if (maxItems > 0 && items.length > maxItems) {
      const startItems = items.slice(0, 2);
      const endItems = items.slice(-2);
      hiddenCount = items.length - 4;
      displayItems = [...startItems, { label: collapseLabel, href: undefined } as BreadcrumbItem, ...endItems];
    }

    const handleItemClick = (item: BreadcrumbItem, index: number) => {
      if (!item.href && !item.active) return;
      onItemClick?.(item);
    };

    return (
      <nav
        ref={ref}
        aria-label="Breadcrumb"
        className={cn(
          'flex items-center text-sm text-gray-500 dark:text-gray-400',
          className
        )}
        {...props}
      >
        <ol className="flex flex-wrap items-center gap-1.5">
          {displayItems.map((item, index) => {
            const isLast = index === displayItems.length - 1;
            const isHidden = item.label === collapseLabel;

            return (
              <React.Fragment key={index}>
                <li
                  className={cn(
                    'flex items-center gap-1.5',
                    isLast && 'text-gray-900 dark:text-white font-medium'
                  )}
                >
                  {item.icon && (
                    <span className="flex-shrink-0">{item.icon}</span>
                  )}
                  {item.href && !isHidden ? (
                    <Link
                      href={item.href}
                      className={cn(
                        'transition-colors hover:text-gray-700 dark:hover:text-gray-300',
                        capitalize && 'capitalize',
                        isLast && 'pointer-events-none'
                      )}
                      onClick={() => handleItemClick(item, index)}
                    >
                      {item.label}
                    </Link>
                  ) : (
                    <span
                      className={cn(
                        capitalize && 'capitalize',
                        isHidden && 'text-gray-400 dark:text-gray-500'
                      )}
                    >
                      {item.label}
                    </span>
                  )}
                </li>
                {!isLast && (
                  <li
                    className="flex items-center text-gray-400 dark:text-gray-500"
                    aria-hidden="true"
                  >
                    {separator}
                  </li>
                )}
              </React.Fragment>
            );
          })}
          {hiddenCount > 0 && (
            <li className="text-xs text-gray-400 dark:text-gray-500">
              ({hiddenCount} autres)
            </li>
          )}
        </ol>
      </nav>
    );
  }
);
Breadcrumb.displayName = 'Breadcrumb';

// ============================================
// SOUS-COMPOSANTS
// ============================================

const BreadcrumbList = React.forwardRef<HTMLOListElement, BreadcrumbListProps>(
  ({ className, ...props }, ref) => (
    <ol
      ref={ref}
      className={cn(
        'flex flex-wrap items-center gap-1.5 break-words text-sm text-gray-500 dark:text-gray-400 sm:gap-2.5',
        className
      )}
      {...props}
    />
  )
);
BreadcrumbList.displayName = 'BreadcrumbList';

const BreadcrumbItem = React.forwardRef<HTMLLIElement, BreadcrumbItemProps>(
  ({ className, href, isCurrent, icon, children, ...props }, ref) => (
    <li
      ref={ref}
      className={cn(
        'inline-flex items-center gap-1.5',
        isCurrent && 'font-medium text-gray-900 dark:text-white',
        className
      )}
      aria-current={isCurrent ? 'page' : undefined}
      {...props}
    >
      {icon && <span className="flex-shrink-0">{icon}</span>}
      {href ? (
        <Link
          href={href}
          className={cn(
            'transition-colors hover:text-gray-700 dark:hover:text-gray-300',
            isCurrent && 'pointer-events-none'
          )}
        >
          {children}
        </Link>
      ) : (
        <span>{children}</span>
      )}
    </li>
  )
);
BreadcrumbItem.displayName = 'BreadcrumbItem';

const BreadcrumbLink = React.forwardRef<HTMLAnchorElement, BreadcrumbLinkProps>(
  ({ className, asChild, ...props }, ref) => {
    const Comp = asChild ? 'span' : Link;
    return (
      <Comp
        ref={ref}
        className={cn(
          'transition-colors hover:text-gray-700 dark:hover:text-gray-300',
          className
        )}
        {...props}
      />
    );
  }
);
BreadcrumbLink.displayName = 'BreadcrumbLink';

const BreadcrumbPage = React.forwardRef<HTMLSpanElement, BreadcrumbPageProps>(
  ({ className, ...props }, ref) => (
    <span
      ref={ref}
      className={cn('font-normal text-gray-900 dark:text-white', className)}
      aria-current="page"
      {...props}
    />
  )
);
BreadcrumbPage.displayName = 'BreadcrumbPage';

const BreadcrumbSeparator = React.forwardRef<
  HTMLSpanElement,
  BreadcrumbSeparatorProps
>(({ className, children, ...props }, ref) => (
  <span
    ref={ref}
    className={cn('text-gray-400 dark:text-gray-500', className)}
    role="presentation"
    aria-hidden="true"
    {...props}
  >
    {children || <Slash className="h-4 w-4" />}
  </span>
));
BreadcrumbSeparator.displayName = 'BreadcrumbSeparator';

// ============================================
// EXPORTATIONS
// ============================================

export {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbPage,
  BreadcrumbSeparator,
};

export default Breadcrumb;

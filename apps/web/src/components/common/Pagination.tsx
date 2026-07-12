// apps/web/src/components/common/Pagination.tsx
'use client';

import React, {
  ReactNode,
  useState,
  useEffect,
  useCallback,
  useMemo,
  forwardRef,
  Ref,
  createContext,
  useContext,
  useId,
} from 'react';
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
  EllipsisHorizontalIcon,
  ArrowPathIcon,
  MagnifyingGlassIcon,
  AdjustmentsHorizontalIcon,
  Squares2X2Icon,
  ListBulletIcon,
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/common/Select';
import { Input } from '@/components/common/Input';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/common/Popover';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Checkbox } from '@/components/common/Checkbox';
import { Separator } from '@/components/common/Separator';

// ============================================================================
// TYPES
// ============================================================================

export type PaginationVariant = 'default' | 'compact' | 'minimal' | 'rounded' | 'outlined' | 'pill';

export type PaginationSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

export type PaginationAlignment = 'left' | 'center' | 'right' | 'between';

export type PaginationEllipsis = 'both' | 'start' | 'end' | 'none';

export type PageSizeOption = number | { label: string; value: number };

export interface PaginationProps {
  // --- Contrôle ---
  /** Nombre total d'éléments */
  totalItems: number;
  /** Nombre d'éléments par page */
  pageSize?: number;
  /** Page courante (1-indexed) */
  currentPage?: number;
  /** Callback lors du changement de page */
  onPageChange?: (page: number) => void;
  /** Callback lors du changement de taille de page */
  onPageSizeChange?: (size: number) => void;

  // --- Apparence ---
  /** Variante d'affichage */
  variant?: PaginationVariant;
  /** Taille des éléments */
  size?: PaginationSize;
  /** Alignement */
  alignment?: PaginationAlignment;
  /** Nombre maximal de pages affichées */
  maxVisiblePages?: number;
  /** Afficher les ellipses */
  showEllipsis?: PaginationEllipsis;
  /** Afficher les infos (total, range) */
  showInfo?: boolean;
  /** Afficher le sélecteur de taille de page */
  showPageSizeSelector?: boolean;
  /** Afficher le champ de saut de page */
  showJumpToPage?: boolean;
  /** Afficher les boutons de navigation (Premier/Dernier) */
  showNavButtons?: boolean;
  /** Afficher les boutons Précédent/Suivant */
  showPrevNextButtons?: boolean;
  /** Afficher la barre de progression */
  showProgress?: boolean;
  /** Afficher le résumé */
  showSummary?: boolean;
  /** Afficher les icônes */
  showIcons?: boolean;
  /** Afficher les libellés */
  showLabels?: boolean;

  // --- Options ---
  /** Options de taille de page */
  pageSizeOptions?: number[] | PageSizeOption[];
  /** Taille de page par défaut */
  defaultPageSize?: number;
  /** Page par défaut */
  defaultPage?: number;
  /** Nombre minimum d'éléments pour afficher la pagination */
  minItems?: number;

  // --- Personnalisation ---
  /** Classe CSS additionnelle */
  className?: string;
  /** Classe CSS pour le conteneur */
  containerClassName?: string;
  /** Classe CSS pour les boutons */
  buttonClassName?: string;
  /** Classe CSS pour les boutons actifs */
  activeClassName?: string;
  /** Classe CSS pour les ellipses */
  ellipsisClassName?: string;
  /** Classe CSS pour les infos */
  infoClassName?: string;
  /** Classe CSS pour le sélecteur */
  selectorClassName?: string;
  /** Classe CSS pour la barre de progression */
  progressClassName?: string;

  // --- Internationalisation ---
  /** Libellé "Page" */
  labelPage?: string;
  /** Libellé "Sur" */
  labelOf?: string;
  /** Libellé "Éléments" */
  labelItems?: string;
  /** Libellé "Aller à" */
  labelJumpTo?: string;
  /** Libellé "Précédent" */
  labelPrevious?: string;
  /** Libellé "Suivant" */
  labelNext?: string;
  /** Libellé "Premier" */
  labelFirst?: string;
  /** Libellé "Dernier" */
  labelLast?: string;
  /** Libellé "Ligne" */
  labelRows?: string;
  /** Libellé "Lignes par page" */
  labelRowsPerPage?: string;

  // --- États ---
  /** État de chargement */
  isLoading?: boolean;
  /** État d'erreur */
  error?: string | null;
  /** Désactiver la pagination */
  disabled?: boolean;

  // --- Accessibilité ---
  /** ARIA label pour la navigation */
  ariaLabel?: string;
  /** ARIA label pour la page courante */
  ariaCurrent?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Fonction de rendu personnalisée pour les boutons */
  renderButton?: (props: RenderButtonProps) => ReactNode;
  /** Fonction de rendu personnalisée pour les infos */
  renderInfo?: (props: RenderInfoProps) => ReactNode;
  /** Fonction de rendu personnalisée pour le résumé */
  renderSummary?: (props: RenderSummaryProps) => ReactNode;
  /** Fonction de rendu personnalisée pour les ellipses */
  renderEllipsis?: () => ReactNode;
  /** Callback pour le chargement automatique */
  onLoadMore?: () => void;
  /** Seuil de chargement automatique (pour l'infini) */
  infiniteScrollThreshold?: number;
  /** Mode chargement infini */
  infiniteScroll?: boolean;
  /** Élément pour déclencher le chargement infini */
  scrollTargetRef?: React.RefObject<HTMLElement>;
}

// --- Props de rendu ---
export interface RenderButtonProps {
  page: number;
  isActive: boolean;
  isDisabled: boolean;
  label: string;
  onClick: () => void;
  className?: string;
}

export interface RenderInfoProps {
  currentPage: number;
  pageSize: number;
  totalItems: number;
  startItem: number;
  endItem: number;
  totalPages: number;
}

export interface RenderSummaryProps {
  currentPage: number;
  pageSize: number;
  totalItems: number;
  startItem: number;
  endItem: number;
  totalPages: number;
}

// ============================================================================
// CONTEXT
// ============================================================================

interface PaginationContextType {
  currentPage: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
  startItem: number;
  endItem: number;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
  variant: PaginationVariant;
  size: PaginationSize;
  disabled: boolean;
  isLoading: boolean;
}

const PaginationContext = createContext<PaginationContextType | null>(null);

export const usePaginationContext = () => {
  const context = useContext(PaginationContext);
  if (!context) {
    throw new Error('usePaginationContext must be used within a Pagination');
  }
  return context;
};

// ============================================================================
// COMPOSANTS INTERNES
// ============================================================================

// --- Progression ---
interface ProgressBarProps {
  current: number;
  total: number;
  className?: string;
}

const ProgressBar: React.FC<ProgressBarProps> = ({ current, total, className }) => {
  const percentage = Math.min(100, (current / total) * 100);

  return (
    <div className={cn('relative w-full h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden', className)}>
      <motion.div
        className="absolute inset-y-0 left-0 bg-brand-500 rounded-full"
        initial={{ width: 0 }}
        animate={{ width: `${percentage}%` }}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
      />
    </div>
  );
};

// --- PageButton ---
interface PageButtonProps {
  page: number;
  isActive?: boolean;
  isDisabled?: boolean;
  onClick: (page: number) => void;
  variant?: PaginationVariant;
  size?: PaginationSize;
  className?: string;
  activeClassName?: string;
  children?: ReactNode;
  ariaLabel?: string;
}

const PageButton: React.FC<PageButtonProps> = ({
  page,
  isActive = false,
  isDisabled = false,
  onClick,
  variant = 'default',
  size = 'md',
  className,
  activeClassName,
  children,
  ariaLabel,
}) => {
  const sizeClasses = {
    xs: 'h-6 w-6 text-xs',
    sm: 'h-8 w-8 text-sm',
    md: 'h-9 w-9 text-sm',
    lg: 'h-10 w-10 text-base',
    xl: 'h-12 w-12 text-lg',
  };

  const variantClasses = {
    default: cn(
      'rounded-md border border-transparent',
      isActive
        ? 'bg-brand-500 text-white hover:bg-brand-600 dark:bg-brand-600 dark:hover:bg-brand-700'
        : 'bg-transparent text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
    ),
    compact: cn(
      'rounded',
      isActive
        ? 'bg-brand-500 text-white hover:bg-brand-600 dark:bg-brand-600 dark:hover:bg-brand-700'
        : 'bg-transparent text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
    ),
    minimal: cn(
      'rounded-none border-0',
      isActive
        ? 'bg-brand-500 text-white hover:bg-brand-600 dark:bg-brand-600 dark:hover:bg-brand-700'
        : 'bg-transparent text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
    ),
    rounded: cn(
      'rounded-full',
      isActive
        ? 'bg-brand-500 text-white hover:bg-brand-600 dark:bg-brand-600 dark:hover:bg-brand-700'
        : 'bg-transparent text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
    ),
    outlined: cn(
      'rounded-md border',
      isActive
        ? 'border-brand-500 bg-brand-50 text-brand-700 hover:bg-brand-100 dark:border-brand-400 dark:bg-brand-900/30 dark:text-brand-400'
        : 'border-gray-300 bg-transparent text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800'
    ),
    pill: cn(
      'rounded-full border border-transparent',
      isActive
        ? 'bg-brand-500 text-white hover:bg-brand-600 dark:bg-brand-600 dark:hover:bg-brand-700'
        : 'bg-transparent text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
    ),
  };

  return (
    <button
      className={cn(
        'flex items-center justify-center font-medium transition-all focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed',
        sizeClasses[size],
        variantClasses[variant],
        isActive && activeClassName,
        className
      )}
      onClick={() => !isDisabled && onClick(page)}
      disabled={isDisabled || isActive}
      aria-label={ariaLabel || `Page ${page}`}
      aria-current={isActive ? 'page' : undefined}
    >
      {children || page}
    </button>
  );
};

// --- NavigationButton ---
interface NavigationButtonProps {
  direction: 'prev' | 'next' | 'first' | 'last';
  onClick: () => void;
  disabled?: boolean;
  variant?: PaginationVariant;
  size?: PaginationSize;
  label?: string;
  icon?: ReactNode;
  className?: string;
  ariaLabel?: string;
}

const NavigationButton: React.FC<NavigationButtonProps> = ({
  direction,
  onClick,
  disabled = false,
  variant = 'default',
  size = 'md',
  label,
  icon,
  className,
  ariaLabel,
}) => {
  const sizeClasses = {
    xs: 'h-6 w-6 text-xs',
    sm: 'h-8 w-8 text-sm',
    md: 'h-9 w-9 text-sm',
    lg: 'h-10 w-10 text-base',
    xl: 'h-12 w-12 text-lg',
  };

  const variantClasses = {
    default: 'rounded-md border border-transparent bg-transparent text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800',
    compact: 'rounded bg-transparent text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800',
    minimal: 'rounded-none border-0 bg-transparent text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800',
    rounded: 'rounded-full bg-transparent text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800',
    outlined: 'rounded-md border border-gray-300 bg-transparent text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800',
    pill: 'rounded-full border border-transparent bg-transparent text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800',
  };

  const defaultIcons = {
    first: <ChevronDoubleLeftIcon className="h-4 w-4" />,
    prev: <ChevronLeftIcon className="h-4 w-4" />,
    next: <ChevronRightIcon className="h-4 w-4" />,
    last: <ChevronDoubleRightIcon className="h-4 w-4" />,
  };

  const defaultLabels = {
    first: 'Premier',
    prev: 'Précédent',
    next: 'Suivant',
    last: 'Dernier',
  };

  const finalIcon = icon || defaultIcons[direction];
  const finalLabel = label || defaultLabels[direction];

  return (
    <button
      className={cn(
        'flex items-center justify-center gap-1 font-medium transition-all focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed',
        sizeClasses[size],
        variantClasses[variant],
        className
      )}
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel || finalLabel}
    >
      {finalIcon}
      {label && <span className="hidden sm:inline">{label}</span>}
    </button>
  );
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const Pagination = forwardRef<HTMLDivElement, PaginationProps>(
  (props, ref) => {
    const {
      // Contrôle
      totalItems,
      pageSize: externalPageSize,
      currentPage: externalCurrentPage,
      onPageChange,
      onPageSizeChange,

      // Apparence
      variant = 'default',
      size = 'md',
      alignment = 'center',
      maxVisiblePages = 5,
      showEllipsis = 'both',
      showInfo = true,
      showPageSizeSelector = true,
      showJumpToPage = true,
      showNavButtons = true,
      showPrevNextButtons = true,
      showProgress = false,
      showSummary = false,
      showIcons = true,
      showLabels = false,

      // Options
      pageSizeOptions = [10, 25, 50, 100],
      defaultPageSize = 10,
      defaultPage = 1,
      minItems = 0,

      // Personnalisation
      className,
      containerClassName,
      buttonClassName,
      activeClassName,
      ellipsisClassName,
      infoClassName,
      selectorClassName,
      progressClassName,

      // Internationalisation
      labelPage = 'Page',
      labelOf = 'sur',
      labelItems = 'éléments',
      labelJumpTo = 'Aller à',
      labelPrevious = 'Précédent',
      labelNext = 'Suivant',
      labelFirst = 'Premier',
      labelLast = 'Dernier',
      labelRows = 'Lignes',
      labelRowsPerPage = 'Lignes par page',

      // États
      isLoading = false,
      error = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Pagination',
      ariaCurrent = 'page',
      id,

      // Avancé
      renderButton,
      renderInfo,
      renderSummary,
      renderEllipsis,
      onLoadMore,
      infiniteScrollThreshold = 100,
      infiniteScroll = false,
      scrollTargetRef,
    } = props;

    // ========================================================================
    // ÉTATS INTERNES
    // ========================================================================

    const [internalCurrentPage, setInternalCurrentPage] = useState(defaultPage);
    const [internalPageSize, setInternalPageSize] = useState(
      externalPageSize || defaultPageSize
    );
    const [jumpToValue, setJumpToValue] = useState('');
    const [isLoadingMore, setIsLoadingMore] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const currentPage = externalCurrentPage || internalCurrentPage;
    const pageSize = externalPageSize || internalPageSize;
    const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));

    const startItem = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
    const endItem = Math.min(currentPage * pageSize, totalItems);

    const hasItems = totalItems > 0;
    const showPagination = hasItems && totalItems > minItems;

    const isFirstPage = currentPage === 1;
    const isLastPage = currentPage === totalPages;

    // ========================================================================
    // UTILITIES
    // ========================================================================

    const setPage = useCallback(
      (page: number) => {
        const newPage = Math.max(1, Math.min(page, totalPages));
        if (newPage !== currentPage) {
          if (externalCurrentPage === undefined) {
            setInternalCurrentPage(newPage);
          }
          if (onPageChange) {
            onPageChange(newPage);
          }
        }
      },
      [currentPage, totalPages, externalCurrentPage, onPageChange]
    );

    const setPageSize = useCallback(
      (size: number) => {
        if (size !== pageSize) {
          if (externalPageSize === undefined) {
            setInternalPageSize(size);
          }
          if (onPageSizeChange) {
            onPageSizeChange(size);
          }
          // Reset to first page when changing page size
          setPage(1);
        }
      },
      [pageSize, externalPageSize, onPageSizeChange, setPage]
    );

    const goToFirst = useCallback(() => setPage(1), [setPage]);
    const goToLast = useCallback(() => setPage(totalPages), [setPage, totalPages]);
    const goToPrevious = useCallback(() => setPage(currentPage - 1), [setPage, currentPage]);
    const goToNext = useCallback(() => setPage(currentPage + 1), [setPage, currentPage]);

    // ========================================================================
    // CALCUL DES PAGES VISIBLES
    // ========================================================================

    const getVisiblePages = useCallback(() => {
      const visiblePages: (number | 'ellipsis')[] = [];

      if (totalPages <= maxVisiblePages + 2) {
        // Show all pages
        for (let i = 1; i <= totalPages; i++) {
          visiblePages.push(i);
        }
        return visiblePages;
      }

      const half = Math.floor(maxVisiblePages / 2);

      let startPage = Math.max(1, currentPage - half);
      let endPage = Math.min(totalPages, currentPage + half);

      if (endPage - startPage < maxVisiblePages - 1) {
        if (startPage === 1) {
          endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
        } else if (endPage === totalPages) {
          startPage = Math.max(1, endPage - maxVisiblePages + 1);
        }
      }

      const showStartEllipsis = showEllipsis === 'both' || showEllipsis === 'start';
      const showEndEllipsis = showEllipsis === 'both' || showEllipsis === 'end';

      if (startPage > 1) {
        visiblePages.push(1);
        if (startPage > 2 && showStartEllipsis) {
          visiblePages.push('ellipsis');
        }
      }

      for (let i = startPage; i <= endPage; i++) {
        visiblePages.push(i);
      }

      if (endPage < totalPages) {
        if (endPage < totalPages - 1 && showEndEllipsis) {
          visiblePages.push('ellipsis');
        }
        visiblePages.push(totalPages);
      }

      return visiblePages;
    }, [totalPages, currentPage, maxVisiblePages, showEllipsis]);

    const visiblePages = getVisiblePages();

    // ========================================================================
    // CHARGEMENT INFINI
    // ========================================================================

    useEffect(() => {
      if (!infiniteScroll || !onLoadMore || isLoadingMore || isLastPage) return;

      const target = scrollTargetRef?.current || window;
      const element = 'addEventListener' in target ? target : window;

      const handleScroll = () => {
        const scrollElement = scrollTargetRef?.current || document.documentElement;
        const scrollY = 'scrollY' in element ? element.scrollY : scrollElement.scrollTop;
        const height = scrollElement.scrollHeight || document.documentElement.scrollHeight;
        const clientHeight = scrollElement.clientHeight || window.innerHeight;

        if (scrollY + clientHeight >= height - infiniteScrollThreshold) {
          setIsLoadingMore(true);
          onLoadMore?.();
        }
      };

      element.addEventListener('scroll', handleScroll);
      return () => element.removeEventListener('scroll', handleScroll);
    }, [infiniteScroll, onLoadMore, isLastPage, isLoadingMore, scrollTargetRef, infiniteScrollThreshold]);

    // Reset loading more state
    useEffect(() => {
      setIsLoadingMore(false);
    }, [currentPage]);

    // ========================================================================
    // CONTEXT
    // ========================================================================

    const contextValue = useMemo<PaginationContextType>(
      () => ({
        currentPage,
        pageSize,
        totalItems,
        totalPages,
        startItem,
        endItem,
        setPage,
        setPageSize,
        variant,
        size,
        disabled,
        isLoading,
      }),
      [
        currentPage,
        pageSize,
        totalItems,
        totalPages,
        startItem,
        endItem,
        setPage,
        setPageSize,
        variant,
        size,
        disabled,
        isLoading,
      ]
    );

    // ========================================================================
    // RENDU
    // ========================================================================

    if (!showPagination && !infiniteScroll) {
      return null;
    }

    if (error) {
      return (
        <div className="flex items-center justify-center p-4 text-red-600 dark:text-red-400">
          <ExclamationTriangleIcon className="h-5 w-5 mr-2" />
          <span>{error}</span>
        </div>
      );
    }

    // --- Rendu des boutons de page ---
    const renderPageButtons = () => {
      return (
        <div className="flex items-center gap-0.5">
          {/* Bouton Premier */}
          {showNavButtons && (
            <NavigationButton
              direction="first"
              onClick={goToFirst}
              disabled={isFirstPage || disabled || isLoading}
              variant={variant}
              size={size}
              label={showLabels ? labelFirst : undefined}
              className={buttonClassName}
            />
          )}

          {/* Bouton Précédent */}
          {showPrevNextButtons && (
            <NavigationButton
              direction="prev"
              onClick={goToPrevious}
              disabled={isFirstPage || disabled || isLoading}
              variant={variant}
              size={size}
              label={showLabels ? labelPrevious : undefined}
              className={buttonClassName}
            />
          )}

          {/* Pages */}
          {visiblePages.map((page, index) => {
            if (page === 'ellipsis') {
              return renderEllipsis ? (
                renderEllipsis()
              ) : (
                <span
                  key={`ellipsis-${index}`}
                  className={cn(
                    'flex items-center justify-center text-gray-400 dark:text-gray-500',
                    size === 'xs' && 'h-6 w-6 text-xs',
                    size === 'sm' && 'h-8 w-8 text-sm',
                    size === 'md' && 'h-9 w-9 text-sm',
                    size === 'lg' && 'h-10 w-10 text-base',
                    size === 'xl' && 'h-12 w-12 text-lg',
                    ellipsisClassName
                  )}
                >
                  <EllipsisHorizontalIcon className="h-4 w-4" />
                </span>
              );
            }

            const isActive = page === currentPage;

            if (renderButton) {
              return renderButton({
                page,
                isActive,
                isDisabled: disabled || isLoading,
                label: String(page),
                onClick: () => setPage(page),
                className: cn(
                  isActive && activeClassName,
                  buttonClassName
                ),
              });
            }

            return (
              <PageButton
                key={page}
                page={page}
                isActive={isActive}
                isDisabled={disabled || isLoading}
                onClick={setPage}
                variant={variant}
                size={size}
                className={buttonClassName}
                activeClassName={activeClassName}
                ariaLabel={`${labelPage} ${page}`}
              />
            );
          })}

          {/* Bouton Suivant */}
          {showPrevNextButtons && (
            <NavigationButton
              direction="next"
              onClick={goToNext}
              disabled={isLastPage || disabled || isLoading}
              variant={variant}
              size={size}
              label={showLabels ? labelNext : undefined}
              className={buttonClassName}
            />
          )}

          {/* Bouton Dernier */}
          {showNavButtons && (
            <NavigationButton
              direction="last"
              onClick={goToLast}
              disabled={isLastPage || disabled || isLoading}
              variant={variant}
              size={size}
              label={showLabels ? labelLast : undefined}
              className={buttonClassName}
            />
          )}
        </div>
      );
    };

    // --- Rendu des infos ---
    const renderInfoContent = () => {
      const info = {
        currentPage,
        pageSize,
        totalItems,
        startItem,
        endItem,
        totalPages,
      };

      if (renderInfo) {
        return renderInfo(info);
      }

      return (
        <span className={cn('text-sm text-gray-600 dark:text-gray-400', infoClassName)}>
          {hasItems ? (
            <>
              {startItem} - {endItem} {labelOf} {totalItems} {labelItems}
            </>
          ) : (
            `0 ${labelItems}`
          )}
        </span>
      );
    };

    // --- Rendu du résumé ---
    const renderSummaryContent = () => {
      const summary = {
        currentPage,
        pageSize,
        totalItems,
        startItem,
        endItem,
        totalPages,
      };

      if (renderSummary) {
        return renderSummary(summary);
      }

      return (
        <div className="flex items-center gap-3 text-sm text-gray-600 dark:text-gray-400">
          <span>
            {hasItems ? (
              <>
                {startItem} - {endItem} {labelOf} {totalItems}
              </>
            ) : (
              `0 ${labelItems}`
            )}
          </span>
          <Separator orientation="vertical" className="h-4" />
          <span>
            {labelPage} {currentPage} {labelOf} {totalPages}
          </span>
        </div>
      );
    };

    // --- Rendu du sélecteur de taille ---
    const renderPageSizeSelector = () => {
      const options = pageSizeOptions.map((opt) =>
        typeof opt === 'number' ? { label: String(opt), value: opt } : opt
      );

      return (
        <div className="flex items-center gap-2">
          <Label htmlFor="page-size-select" className="text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap">
            {labelRowsPerPage}
          </Label>
          <Select
            value={String(pageSize)}
            onValueChange={(value) => setPageSize(Number(value))}
            disabled={disabled || isLoading}
          >
            <SelectTrigger
              id="page-size-select"
              className={cn('w-20', selectorClassName)}
              size={size === 'xs' || size === 'sm' ? 'sm' : 'md'}
            >
              <SelectValue placeholder={String(pageSize)} />
            </SelectTrigger>
            <SelectContent>
              {options.map((opt) => (
                <SelectItem key={opt.value} value={String(opt.value)}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      );
    };

    // --- Rendu du champ de saut de page ---
    const renderJumpToPage = () => {
      return (
        <div className="flex items-center gap-2">
          <Label htmlFor="jump-to-page" className="text-sm text-gray-600 dark:text-gray-400 hidden sm:block">
            {labelJumpTo}
          </Label>
          <Input
            id="jump-to-page"
            type="number"
            min={1}
            max={totalPages}
            value={jumpToValue}
            onChange={(e) => setJumpToValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                const page = Number(jumpToValue);
                if (page >= 1 && page <= totalPages) {
                  setPage(page);
                  setJumpToValue('');
                }
              }
            }}
            onBlur={() => {
              const page = Number(jumpToValue);
              if (page >= 1 && page <= totalPages) {
                setPage(page);
              }
              setJumpToValue('');
            }}
            placeholder="Page"
            className={cn('w-16 text-center', size === 'xs' || size === 'sm' ? 'h-8 text-sm' : 'h-9')}
            disabled={disabled || isLoading}
          />
        </div>
      );
    };

    // --- Rendu principal ---
    const alignmentClasses = {
      left: 'justify-start',
      center: 'justify-center',
      right: 'justify-end',
      between: 'justify-between',
    };

    return (
      <PaginationContext.Provider value={contextValue}>
        <div
          ref={ref}
          id={id}
          className={cn(
            'flex flex-wrap items-center gap-2 py-2',
            alignmentClasses[alignment],
            className,
            containerClassName
          )}
          role="navigation"
          aria-label={ariaLabel}
        >
          {/* Info à gauche */}
          {(alignment === 'left' || alignment === 'between') && showInfo && (
            <div className="flex items-center gap-3">
              {renderInfoContent()}
            </div>
          )}

          {/* Sélecteur de taille à gauche */}
          {(alignment === 'left' || alignment === 'between') && showPageSizeSelector && (
            renderPageSizeSelector()
          )}

          {/* Boutons de pagination */}
          <div className="flex flex-wrap items-center gap-1">
            {renderPageButtons()}
          </div>

          {/* Sélecteur de taille à droite */}
          {(alignment === 'right' || alignment === 'between') && showPageSizeSelector && (
            renderPageSizeSelector()
          )}

          {/* Info à droite */}
          {(alignment === 'right' || alignment === 'between') && showInfo && (
            <div className="flex items-center gap-3">
              {renderInfoContent()}
            </div>
          )}

          {/* Saut de page */}
          {showJumpToPage && (
            renderJumpToPage()
          )}

          {/* Résumé */}
          {showSummary && (
            <div className="w-full text-center">
              {renderSummaryContent()}
            </div>
          )}

          {/* Barre de progression */}
          {showProgress && (
            <div className={cn('w-full', progressClassName)}>
              <ProgressBar current={currentPage} total={totalPages} />
            </div>
          )}

          {/* Chargement infini */}
          {infiniteScroll && isLoadingMore && (
            <div className="flex w-full items-center justify-center gap-2 py-2 text-sm text-gray-500 dark:text-gray-400">
              <ArrowPathIcon className="h-4 w-4 animate-spin" />
              <span>Chargement...</span>
            </div>
          )}
        </div>
      </PaginationContext.Provider>
    );
  }
);

Pagination.displayName = 'Pagination';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

interface PaginationInfoProps {
  className?: string;
  children?: ReactNode;
  format?: 'simple' | 'detailed' | 'custom';
}

export const PaginationInfo: React.FC<PaginationInfoProps> = ({
  className,
  children,
  format = 'detailed',
}) => {
  const context = usePaginationContext();
  const { currentPage, pageSize, totalItems, startItem, endItem, totalPages } = context;

  if (children) {
    return <div className={className}>{children}</div>;
  }

  const formatMap = {
    simple: `${currentPage} / ${totalPages}`,
    detailed: `${startItem} - ${endItem} sur ${totalItems}`,
    custom: `Page ${currentPage} sur ${totalPages} (${totalItems} éléments)`,
  };

  return (
    <span className={cn('text-sm text-gray-600 dark:text-gray-400', className)}>
      {formatMap[format]}
    </span>
  );
};

interface PaginationSummaryProps {
  className?: string;
  children?: ReactNode;
}

export const PaginationSummary: React.FC<PaginationSummaryProps> = ({
  className,
  children,
}) => {
  const context = usePaginationContext();
  const { currentPage, totalPages, totalItems } = context;

  if (children) {
    return <div className={className}>{children}</div>;
  }

  return (
    <div className={cn('flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400', className)}>
      <Badge variant="outline" className="font-mono">
        {totalItems} éléments
      </Badge>
      <span>•</span>
      <Badge variant="outline" className="font-mono">
        Page {currentPage} / {totalPages}
      </Badge>
    </div>
  );
};

// ============================================================================
// HOOKS
// ============================================================================

export const usePagination = (options: {
  totalItems: number;
  pageSize?: number;
  defaultPageSize?: number;
  defaultPage?: number;
  onPageChange?: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
}) => {
  const {
    totalItems,
    pageSize: externalPageSize,
    defaultPageSize = 10,
    defaultPage = 1,
    onPageChange,
    onPageSizeChange,
  } = options;

  const [currentPage, setCurrentPage] = useState(defaultPage);
  const [pageSize, setPageSize] = useState(externalPageSize || defaultPageSize);

  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const startItem = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  const setPage = useCallback(
    (page: number) => {
      const newPage = Math.max(1, Math.min(page, totalPages));
      if (newPage !== currentPage) {
        setCurrentPage(newPage);
        if (onPageChange) onPageChange(newPage);
      }
    },
    [currentPage, totalPages, onPageChange]
  );

  const changePageSize = useCallback(
    (size: number) => {
      if (size !== pageSize) {
        setPageSize(size);
        setCurrentPage(1);
        if (onPageSizeChange) onPageSizeChange(size);
      }
    },
    [pageSize, onPageSizeChange]
  );

  const goToFirst = useCallback(() => setPage(1), [setPage]);
  const goToLast = useCallback(() => setPage(totalPages), [setPage, totalPages]);
  const goToPrevious = useCallback(() => setPage(currentPage - 1), [setPage, currentPage]);
  const goToNext = useCallback(() => setPage(currentPage + 1), [setPage, currentPage]);

  return {
    currentPage,
    pageSize,
    totalItems,
    totalPages,
    startItem,
    endItem,
    setPage,
    setPageSize: changePageSize,
    goToFirst,
    goToLast,
    goToPrevious,
    goToNext,
    isFirstPage: currentPage === 1,
    isLastPage: currentPage === totalPages,
  };
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(Pagination, {
  Info: PaginationInfo,
  Summary: PaginationSummary,
});

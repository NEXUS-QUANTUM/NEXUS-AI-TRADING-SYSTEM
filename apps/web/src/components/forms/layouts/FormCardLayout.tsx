// apps/web/src/components/forms/layouts/FormCardLayout.tsx
'use client';

import React, {
  ReactNode,
  forwardRef,
  Ref,
  useRef,
  useState,
  useCallback,
  useEffect,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronDownIcon,
  ChevronUpIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  XMarkIcon,
  CheckIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  Cog6ToothIcon,
  AdjustmentsHorizontalIcon,
  Squares2X2Icon,
  EyeIcon,
  EyeSlashIcon,
  PencilIcon,
  TrashIcon,
  DocumentDuplicateIcon,
  ShareIcon,
  LinkIcon,
  BookmarkIcon,
  HeartIcon,
  StarIcon,
  FlagIcon,
  PrinterIcon,
  EnvelopeIcon,
  ClipboardIcon,
  PlusIcon,
  MinusIcon,
} from '@heroicons/react/24/outline';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { Badge } from '@/components/common/Badge';
import { Separator } from '@/components/common/Separator';
import { Progress } from '@/components/common/Progress';
import { Tooltip } from '@/components/common/Tooltip';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type FormCardVariant = 'default' | 'glass' | 'solid' | 'outlined' | 'shadow' | 'borderless';
export type FormCardSize = 'sm' | 'md' | 'lg' | 'xl';
export type FormCardStatus = 'idle' | 'loading' | 'success' | 'error' | 'warning' | 'info';
export type FormCardAlignment = 'left' | 'center' | 'right' | 'between';
export type FormCardActionPosition = 'top' | 'bottom' | 'both' | 'none';

export interface FormCardSection {
  /** Identifiant de la section */
  id: string;
  /** Titre de la section */
  title?: ReactNode;
  /** Description de la section */
  description?: ReactNode;
  /** Contenu de la section */
  content: ReactNode;
  /** Actions de la section */
  actions?: ReactNode;
  /** Icône de la section */
  icon?: ReactNode;
  /** Statut de la section */
  status?: FormCardStatus;
  /** Est-ce que la section est collapsible */
  collapsible?: boolean;
  /** Est-ce que la section est initialement ouverte */
  defaultOpen?: boolean;
  /** Est-ce que la section est désactivée */
  disabled?: boolean;
  /** Classe additionnelle */
  className?: string;
}

export interface FormCardLayoutProps {
  // --- Contenu ---
  /** Titre de la carte */
  title?: ReactNode;
  /** Sous-titre de la carte */
  subtitle?: ReactNode;
  /** Icône de la carte */
  icon?: ReactNode;
  /** Sections du formulaire */
  sections?: FormCardSection[];
  /** En-tête personnalisé */
  header?: ReactNode;
  /** Pied de page personnalisé */
  footer?: ReactNode;
  /** Enfant (contenu principal) */
  children?: ReactNode;
  /** Actions globales */
  actions?: ReactNode;

  // --- Apparence ---
  /** Variante de la carte */
  variant?: FormCardVariant;
  /** Taille de la carte */
  size?: FormCardSize;
  /** Statut de la carte */
  status?: FormCardStatus;
  /** Alignement du contenu */
  alignment?: FormCardAlignment;
  /** Position des actions */
  actionPosition?: FormCardActionPosition;
  /** Afficher la bordure */
  showBorder?: boolean;
  /** Afficher l'ombre */
  showShadow?: boolean;
  /** Afficher le séparateur entre les sections */
  showSectionSeparator?: boolean;
  /** Afficher les badges de statut */
  showStatusBadges?: boolean;
  /** Afficher les icônes de section */
  showSectionIcons?: boolean;
  /** Afficher le compteur de progression */
  showProgress?: boolean;
  /** Classes additionnelles */
  className?: string;
  /** Classe pour l'en-tête */
  headerClassName?: string;
  /** Classe pour le contenu */
  contentClassName?: string;
  /** Classe pour le pied de page */
  footerClassName?: string;
  /** Classe pour les sections */
  sectionClassName?: string;

  // --- Comportement ---
  /** Désactiver la carte */
  disabled?: boolean;
  /** État de chargement */
  isLoading?: boolean;
  /** Message d'erreur */
  error?: string | null;
  /** Message de succès */
  success?: string | null;
  /** Message d'information */
  info?: string | null;
  /** Message d'avertissement */
  warning?: string | null;
  /** Progression (0-100) */
  progress?: number;
  /** Callback de soumission */
  onSubmit?: () => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de réinitialisation */
  onReset?: () => void;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Désactiver les animations */
  disableAnimations?: boolean;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const VARIANT_MAP: Record<FormCardVariant, string> = {
  default: 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700',
  glass: 'bg-white/80 backdrop-blur-xl dark:bg-gray-900/80 border border-white/20 dark:border-gray-700/50',
  solid: 'bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700',
  outlined: 'bg-transparent border-2 border-gray-200 dark:border-gray-700',
  shadow: 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 shadow-lg',
  borderless: 'bg-white dark:bg-gray-900 border-0',
};

const SIZE_MAP: Record<FormCardSize, { padding: string; title: string; gap: string }> = {
  sm: { padding: 'p-4', title: 'text-base', gap: 'gap-3' },
  md: { padding: 'p-6', title: 'text-lg', gap: 'gap-4' },
  lg: { padding: 'p-8', title: 'text-xl', gap: 'gap-5' },
  xl: { padding: 'p-10', title: 'text-2xl', gap: 'gap-6' },
};

const STATUS_MAP: Record<FormCardStatus, { color: string; icon: React.ReactNode; border: string }> = {
  idle: {
    color: 'text-gray-500 dark:text-gray-400',
    icon: <InformationCircleIcon className="h-5 w-5" />,
    border: 'border-gray-200 dark:border-gray-700',
  },
  loading: {
    color: 'text-brand-500',
    icon: <ArrowPathIcon className="h-5 w-5 animate-spin" />,
    border: 'border-brand-200 dark:border-brand-800',
  },
  success: {
    color: 'text-green-500',
    icon: <CheckCircleIcon className="h-5 w-5" />,
    border: 'border-green-200 dark:border-green-800',
  },
  error: {
    color: 'text-red-500',
    icon: <ExclamationCircleIcon className="h-5 w-5" />,
    border: 'border-red-200 dark:border-red-800',
  },
  warning: {
    color: 'text-yellow-500',
    icon: <ExclamationTriangleIcon className="h-5 w-5" />,
    border: 'border-yellow-200 dark:border-yellow-800',
  },
  info: {
    color: 'text-blue-500',
    icon: <InformationCircleIcon className="h-5 w-5" />,
    border: 'border-blue-200 dark:border-blue-800',
  },
};

// ============================================================================
// SOUS-COMPOSANT: Section
// ============================================================================

interface SectionProps {
  section: FormCardSection;
  index: number;
  isLast: boolean;
  showSeparator: boolean;
  showIcons: boolean;
  showStatusBadges: boolean;
  disabled: boolean;
  className?: string;
  disableAnimations?: boolean;
}

const Section: React.FC<SectionProps> = ({
  section,
  index,
  isLast,
  showSeparator,
  showIcons,
  showStatusBadges,
  disabled,
  className,
  disableAnimations,
}) => {
  const [isOpen, setIsOpen] = useState(section.defaultOpen !== undefined ? section.defaultOpen : true);
  const status = section.status || 'idle';
  const statusMap = STATUS_MAP[status];

  const toggleOpen = useCallback(() => {
    if (section.collapsible) {
      setIsOpen(!isOpen);
    }
  }, [section.collapsible, isOpen]);

  return (
    <div
      className={cn(
        'relative',
        !isLast && showSeparator && 'border-b border-gray-200 dark:border-gray-700 pb-4',
        !isLast && !showSeparator && 'mb-4',
        section.disabled && 'opacity-50 cursor-not-allowed',
        section.className,
        className
      )}
    >
      {/* En-tête de la section */}
      {(section.title || section.description || section.actions || section.icon) && (
        <div
          className={cn(
            'flex items-start gap-3',
            section.collapsible && 'cursor-pointer'
          )}
          onClick={toggleOpen}
        >
          {/* Icône */}
          {showIcons && section.icon && (
            <div className="flex-shrink-0 mt-0.5">
              {section.icon}
            </div>
          )}

          {/* Titre et description */}
          <div className="flex-1 min-w-0">
            {section.title && (
              <div className="flex items-center gap-2">
                <h3 className="font-medium text-gray-900 dark:text-white">
                  {section.title}
                </h3>
                {showStatusBadges && status !== 'idle' && (
                  <Badge
                    variant={
                      status === 'success' ? 'success' :
                      status === 'error' ? 'danger' :
                      status === 'warning' ? 'warning' :
                      status === 'info' ? 'info' :
                      'default'
                    }
                    size="xs"
                  >
                    {status}
                  </Badge>
                )}
                {section.collapsible && (
                  <button
                    type="button"
                    className="ml-auto text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleOpen();
                    }}
                    disabled={disabled || section.disabled}
                  >
                    {isOpen ? (
                      <ChevronUpIcon className="h-4 w-4" />
                    ) : (
                      <ChevronDownIcon className="h-4 w-4" />
                    )}
                  </button>
                )}
              </div>
            )}
            {section.description && (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {section.description}
              </p>
            )}
          </div>

          {/* Actions */}
          {section.actions && (
            <div className="flex-shrink-0 flex items-center gap-1">
              {section.actions}
            </div>
          )}
        </div>
      )}

      {/* Contenu de la section */}
      <AnimatePresence>
        {(!section.collapsible || isOpen) && (
          <motion.div
            initial={!disableAnimations ? { opacity: 0, height: 0 } : {}}
            animate={!disableAnimations ? { opacity: 1, height: 'auto' } : {}}
            exit={!disableAnimations ? { opacity: 0, height: 0 } : {}}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className={cn('mt-3', section.title && 'mt-3')}>
              {section.content}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const FormCardLayout = forwardRef<HTMLDivElement, FormCardLayoutProps>(
  (props, ref) => {
    const {
      // Contenu
      title,
      subtitle,
      icon,
      sections = [],
      header,
      footer,
      children,
      actions,

      // Apparence
      variant = 'default',
      size = 'md',
      status = 'idle',
      alignment = 'left',
      actionPosition = 'bottom',
      showBorder = true,
      showShadow = true,
      showSectionSeparator = true,
      showStatusBadges = true,
      showSectionIcons = true,
      showProgress = false,
      className,
      headerClassName,
      contentClassName,
      footerClassName,
      sectionClassName,

      // Comportement
      disabled = false,
      isLoading = false,
      error = null,
      success = null,
      info = null,
      warning = null,
      progress = 0,
      onSubmit,
      onCancel,
      onReset,

      // Accessibilité
      ariaLabel,
      id,

      // Avancé
      disableAnimations = false,
      debug = false,
    } = props;

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [isExpanded, setIsExpanded] = useState(true);
    const containerRef = useRef<HTMLDivElement>(null);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
    const variantStyles = VARIANT_MAP[variant] || VARIANT_MAP.default;
    const statusMap = STATUS_MAP[status] || STATUS_MAP.idle;

    const hasStatus = status !== 'idle';
    const hasStatusMessage = error || success || info || warning;
    const statusMessage = error || success || info || warning;
    const statusType = error ? 'error' : success ? 'success' : warning ? 'warning' : info ? 'info' : null;
    const statusColor = statusType ? STATUS_MAP[statusType as FormCardStatus]?.color : statusMap.color;

    const hasHeader = title || subtitle || icon || header;
    const hasFooter = footer || actions;
    const hasContent = children || sections.length > 0;

    // ========================================================================
    // GESTIONNAIRES
    // ========================================================================

    const handleSubmit = useCallback(() => {
      if (disabled || isLoading) return;
      if (onSubmit) onSubmit();
    }, [disabled, isLoading, onSubmit]);

    const handleCancel = useCallback(() => {
      if (disabled || isLoading) return;
      if (onCancel) onCancel();
    }, [disabled, isLoading, onCancel]);

    const handleReset = useCallback(() => {
      if (disabled || isLoading) return;
      if (onReset) onReset();
    }, [disabled, isLoading, onReset]);

    // ========================================================================
    // RENDU DE L'EN-TÊTE
    // ========================================================================

    const renderHeader = () => {
      if (header) {
        return (
          <div className={cn('flex items-center justify-between', headerClassName)}>
            {header}
          </div>
        );
      }

      if (!hasHeader) return null;

      return (
        <div className={cn('flex items-start gap-4', headerClassName)}>
          {icon && (
            <div className="flex-shrink-0">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 dark:bg-brand-900/20 text-brand-500">
                {icon}
              </div>
            </div>
          )}
          <div className="flex-1 min-w-0">
            {title && (
              <CardTitle className={cn('text-gray-900 dark:text-white', sizeStyles.title)}>
                {title}
              </CardTitle>
            )}
            {subtitle && (
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {subtitle}
              </p>
            )}
          </div>
          {/* Actions en haut */}
          {actionPosition === 'top' || actionPosition === 'both' ? (
            <div className="flex-shrink-0 flex items-center gap-2">
              {actions}
            </div>
          ) : null}
        </div>
      );
    };

    // ========================================================================
    // RENDU DU STATUT
    // ========================================================================

    const renderStatus = () => {
      if (!hasStatusMessage && !hasStatus) return null;

      return (
        <div
          className={cn(
            'flex items-start gap-2 rounded-lg p-3 text-sm',
            error && 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400',
            success && 'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400',
            warning && 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-600 dark:text-yellow-400',
            info && 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
          )}
        >
          {error && <ExclamationCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />}
          {success && <CheckCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />}
          {warning && <ExclamationTriangleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />}
          {info && <InformationCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />}
          <span>{statusMessage}</span>
        </div>
      );
    };

    // ========================================================================
    // RENDU DU CONTENU
    // ========================================================================

    const renderContent = () => {
      if (isLoading) {
        return (
          <div className="flex flex-col items-center justify-center py-12">
            <ArrowPathIcon className="h-8 w-8 animate-spin text-brand-500" />
            <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
              Chargement...
            </p>
          </div>
        );
      }

      // Si des sections sont définies
      if (sections.length > 0) {
        return (
          <div className="space-y-4">
            {sections.map((section, index) => (
              <Section
                key={section.id}
                section={section}
                index={index}
                isLast={index === sections.length - 1}
                showSeparator={showSectionSeparator}
                showIcons={showSectionIcons}
                showStatusBadges={showStatusBadges}
                disabled={disabled}
                className={sectionClassName}
                disableAnimations={disableAnimations}
              />
            ))}
          </div>
        );
      }

      // Sinon, afficher les enfants
      return children;
    };

    // ========================================================================
    // RENDU DU PIED DE PAGE
    // ========================================================================

    const renderFooter = () => {
      if (footer) {
        return (
          <div className={footerClassName}>
            {footer}
          </div>
        );
      }

      const showActions = (actionPosition === 'bottom' || actionPosition === 'both') && actions;
      const showButtons = onSubmit || onCancel || onReset;

      if (!showActions && !showButtons) return null;

      return (
        <div className={cn(
          'flex flex-wrap items-center gap-3',
          alignment === 'center' && 'justify-center',
          alignment === 'right' && 'justify-end',
          alignment === 'between' && 'justify-between',
          footerClassName
        )}>
          {showActions && (
            <div className="flex items-center gap-2">
              {actions}
            </div>
          )}
          {showButtons && (
            <div className="flex items-center gap-2">
              {onReset && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleReset}
                  disabled={disabled || isLoading}
                >
                  Réinitialiser
                </Button>
              )}
              {onCancel && (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={handleCancel}
                  disabled={disabled || isLoading}
                >
                  Annuler
                </Button>
              )}
              {onSubmit && (
                <Button
                  type="submit"
                  variant="primary"
                  onClick={handleSubmit}
                  disabled={disabled || isLoading}
                  isLoading={isLoading}
                >
                  {isLoading ? 'Envoi...' : 'Soumettre'}
                </Button>
              )}
            </div>
          )}
        </div>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const cardClasses = cn(
      'rounded-xl transition-all',
      variantStyles,
      showBorder && 'border',
      showShadow && 'shadow-sm',
      disabled && 'opacity-60 cursor-not-allowed',
      hasStatus && statusMap.border,
      className
    );

    const contentClasses = cn(
      sizeStyles.padding,
      sizeStyles.gap,
      contentClassName
    );

    return (
      <Card
        ref={ref}
        id={id}
        className={cardClasses}
        aria-label={ariaLabel}
        aria-invalid={!!error}
      >
        {/* Progression */}
        {showProgress && (
          <div className="px-6 pt-6">
            <Progress
              value={progress}
              className="h-1.5"
              variant={
                progress >= 100 ? 'success' :
                progress >= 70 ? 'info' :
                progress >= 30 ? 'warning' :
                'default'
              }
            />
            <div className="mt-1 flex justify-between text-xs text-gray-500 dark:text-gray-400">
              <span>Progression</span>
              <span>{Math.round(progress)}%</span>
            </div>
          </div>
        )}

        {/* En-tête */}
        {hasHeader && (
          <div className={cn(
            'border-b border-gray-200 dark:border-gray-700',
            sizeStyles.padding,
            headerClassName
          )}>
            {renderHeader()}
          </div>
        )}

        {/* Statut */}
        {renderStatus()}

        {/* Contenu */}
        {hasContent && (
          <div className={contentClasses}>
            {renderContent()}
          </div>
        )}

        {/* Pied de page */}
        {hasFooter && (
          <div className={cn(
            'border-t border-gray-200 dark:border-gray-700',
            sizeStyles.padding,
            footerClassName
          )}>
            {renderFooter()}
          </div>
        )}
      </Card>
    );
  }
);

FormCardLayout.displayName = 'FormCardLayout';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- FormCardLayout.Section ---
interface FormCardSectionProps extends FormCardSection {
  children?: ReactNode;
}

export const FormCardSection: React.FC<FormCardSectionProps> = ({
  id,
  title,
  description,
  content,
  actions,
  icon,
  status,
  collapsible,
  defaultOpen,
  disabled,
  className,
  children,
}) => {
  return (
    <div className={className}>
      {(title || description || actions || icon) && (
        <div className="flex items-start gap-3 mb-3">
          {icon && <div className="flex-shrink-0 mt-0.5">{icon}</div>}
          <div className="flex-1 min-w-0">
            {title && <h4 className="font-medium text-gray-900 dark:text-white">{title}</h4>}
            {description && <p className="text-sm text-gray-500 dark:text-gray-400">{description}</p>}
          </div>
          {actions && <div className="flex-shrink-0">{actions}</div>}
        </div>
      )}
      <div>{content || children}</div>
    </div>
  );
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(FormCardLayout, {
  Section: FormCardSection,
});

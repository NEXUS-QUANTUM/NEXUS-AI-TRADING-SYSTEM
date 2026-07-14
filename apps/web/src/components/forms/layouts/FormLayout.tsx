// apps/web/src/components/forms/layouts/FormLayout.tsx
'use client';

import React, {
  ReactNode,
  forwardRef,
  Ref,
  Children,
  isValidElement,
  cloneElement,
} from 'react';
import { cn } from '@/lib/utils';

// ============================================================================
// TYPES
// ============================================================================

export type FormLayoutVariant = 'vertical' | 'horizontal' | 'grid' | 'inline' | 'stacked' | 'columns';
export type FormLayoutSize = 'sm' | 'md' | 'lg' | 'xl';
export type FormLayoutGap = 'none' | 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl';
export type FormLayoutAlign = 'start' | 'center' | 'end' | 'stretch' | 'baseline';
export type FormLayoutJustify = 'start' | 'center' | 'end' | 'between' | 'around' | 'evenly';
export type FormLayoutWrap = 'wrap' | 'nowrap' | 'wrap-reverse';
export type FormLayoutColumns = 1 | 2 | 3 | 4 | 5 | 6 | 8 | 12;

export interface FormLayoutProps {
  // --- Contenu ---
  /** Enfants du layout */
  children: ReactNode;
  /** Étiquettes des champs (pour le layout horizontal) */
  labels?: ReactNode[];
  /** Actions du formulaire */
  actions?: ReactNode;

  // --- Apparence ---
  /** Variante du layout */
  variant?: FormLayoutVariant;
  /** Taille du layout */
  size?: FormLayoutSize;
  /** Espacement entre les éléments */
  gap?: FormLayoutGap;
  /** Alignement vertical */
  align?: FormLayoutAlign;
  /** Alignement horizontal */
  justify?: FormLayoutJustify;
  /** Comportement de wrap */
  wrap?: FormLayoutWrap;
  /** Nombre de colonnes (pour grid) */
  columns?: FormLayoutColumns;
  /** Ratio des colonnes (pour columns) */
  columnRatio?: string;
  /** Classes additionnelles */
  className?: string;
  /** Classes pour le conteneur */
  containerClassName?: string;
  /** Classes pour les champs */
  fieldClassName?: string;
  /** Classes pour les labels */
  labelClassName?: string;
  /** Classes pour les actions */
  actionClassName?: string;

  // --- Comportement ---
  /** Désactiver le layout */
  disabled?: boolean;
  /** Désactiver le padding */
  noPadding?: boolean;
  /** Désactiver le border */
  noBorder?: boolean;
  /** Désactiver le background */
  noBackground?: boolean;
  /** Rendre les champs en pleine largeur */
  fullWidth?: boolean;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const GAP_MAP: Record<FormLayoutGap, string> = {
  none: 'gap-0',
  xs: 'gap-1',
  sm: 'gap-2',
  md: 'gap-4',
  lg: 'gap-6',
  xl: 'gap-8',
  '2xl': 'gap-12',
};

const SIZE_MAP: Record<FormLayoutSize, { padding: string; fontSize: string; label: string; input: string }> = {
  sm: {
    padding: 'p-3',
    fontSize: 'text-sm',
    label: 'text-sm',
    input: 'text-sm',
  },
  md: {
    padding: 'p-4',
    fontSize: 'text-base',
    label: 'text-sm',
    input: 'text-sm',
  },
  lg: {
    padding: 'p-6',
    fontSize: 'text-lg',
    label: 'text-base',
    input: 'text-base',
  },
  xl: {
    padding: 'p-8',
    fontSize: 'text-xl',
    label: 'text-lg',
    input: 'text-lg',
  },
};

const ALIGN_MAP: Record<FormLayoutAlign, string> = {
  start: 'items-start',
  center: 'items-center',
  end: 'items-end',
  stretch: 'items-stretch',
  baseline: 'items-baseline',
};

const JUSTIFY_MAP: Record<FormLayoutJustify, string> = {
  start: 'justify-start',
  center: 'justify-center',
  end: 'justify-end',
  between: 'justify-between',
  around: 'justify-around',
  evenly: 'justify-evenly',
};

const WRAP_MAP: Record<FormLayoutWrap, string> = {
  wrap: 'flex-wrap',
  nowrap: 'flex-nowrap',
  'wrap-reverse': 'flex-wrap-reverse',
};

const COLUMN_MAP: Record<FormLayoutColumns, string> = {
  1: 'grid-cols-1',
  2: 'grid-cols-2',
  3: 'grid-cols-3',
  4: 'grid-cols-4',
  5: 'grid-cols-5',
  6: 'grid-cols-6',
  8: 'grid-cols-8',
  12: 'grid-cols-12',
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const FormLayout = forwardRef<HTMLDivElement, FormLayoutProps>(
  (props, ref) => {
    const {
      // Contenu
      children,
      labels = [],
      actions,

      // Apparence
      variant = 'vertical',
      size = 'md',
      gap = 'md',
      align = 'start',
      justify = 'start',
      wrap = 'wrap',
      columns = 2,
      columnRatio = '1fr 1fr',
      className,
      containerClassName,
      fieldClassName,
      labelClassName,
      actionClassName,

      // Comportement
      disabled = false,
      noPadding = false,
      noBorder = false,
      noBackground = false,
      fullWidth = false,

      // Accessibilité
      ariaLabel = 'Formulaire',
      id,

      // Avancé
      debug = false,
    } = props;

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const gapClass = GAP_MAP[gap] || GAP_MAP.md;
    const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
    const alignClass = ALIGN_MAP[align] || ALIGN_MAP.start;
    const justifyClass = JUSTIFY_MAP[justify] || JUSTIFY_MAP.start;
    const wrapClass = WRAP_MAP[wrap] || WRAP_MAP.wrap;
    const columnClass = COLUMN_MAP[columns] || COLUMN_MAP[2];

    const isVertical = variant === 'vertical';
    const isHorizontal = variant === 'horizontal';
    const isGrid = variant === 'grid';
    const isInline = variant === 'inline';
    const isStacked = variant === 'stacked';
    const isColumns = variant === 'columns';

    const hasLabels = labels.length > 0;

    // ========================================================================
    // EXTRACTION DES ENFANTS
    // ========================================================================

    const childrenArray = Children.toArray(children);
    const fields = childrenArray.filter(
      (child) => isValidElement(child) && child.type !== 'div'
    );

    // ========================================================================
    // RENDU DU LAYOUT VERTICAL
    // ========================================================================

    const renderVertical = () => (
      <div className={cn('flex flex-col', gapClass, fullWidth && 'w-full')}>
        {fields.map((field, index) => (
          <div key={index} className={cn('flex flex-col', fullWidth && 'w-full', fieldClassName)}>
            {field}
          </div>
        ))}
        {actions && (
          <div className={cn('mt-2 flex items-center gap-3', actionClassName)}>
            {actions}
          </div>
        )}
      </div>
    );

    // ========================================================================
    // RENDU DU LAYOUT HORIZONTAL
    // ========================================================================

    const renderHorizontal = () => {
      const fieldItems = fields.map((field, index) => {
        const label = labels[index] || null;

        return (
          <div
            key={index}
            className={cn(
              'flex flex-row items-start',
              gapClass,
              fullWidth && 'w-full',
              fieldClassName
            )}
          >
            {label && (
              <div className={cn(
                'flex-shrink-0 min-w-[120px] pt-2',
                sizeStyles.label,
                labelClassName
              )}>
                {label}
              </div>
            )}
            <div className={cn('flex-1', fullWidth && 'w-full')}>
              {field}
            </div>
          </div>
        );
      });

      return (
        <div className={cn('flex flex-col', gapClass, fullWidth && 'w-full')}>
          {fieldItems}
          {actions && (
            <div className={cn(
              'flex items-center gap-3',
              hasLabels && 'ml-[120px]',
              actionClassName
            )}>
              {actions}
            </div>
          )}
        </div>
      );
    };

    // ========================================================================
    // RENDU DU LAYOUT GRILLE
    // ========================================================================

    const renderGrid = () => (
      <div className={cn(
        'grid',
        columnClass,
        gapClass,
        fullWidth && 'w-full',
        alignClass,
        justifyClass
      )}>
        {fields.map((field, index) => (
          <div key={index} className={cn('flex flex-col', fieldClassName)}>
            {field}
          </div>
        ))}
        {actions && (
          <div className={cn('col-span-full flex items-center gap-3', actionClassName)}>
            {actions}
          </div>
        )}
      </div>
    );

    // ========================================================================
    // RENDU DU LAYOUT INLINE
    // ========================================================================

    const renderInline = () => (
      <div className={cn(
        'flex flex-row flex-wrap',
        gapClass,
        alignClass,
        justifyClass,
        wrapClass,
        fullWidth && 'w-full'
      )}>
        {fields.map((field, index) => (
          <div key={index} className={cn('flex-shrink-0', fieldClassName)}>
            {field}
          </div>
        ))}
        {actions && (
          <div className={cn('flex items-center gap-3', actionClassName)}>
            {actions}
          </div>
        )}
      </div>
    );

    // ========================================================================
    // RENDU DU LAYOUT STACKED
    // ========================================================================

    const renderStacked = () => {
      const fieldItems = fields.map((field, index) => {
        const label = labels[index] || null;

        return (
          <div
            key={index}
            className={cn(
              'flex flex-col',
              fullWidth && 'w-full',
              fieldClassName
            )}
          >
            {label && (
              <div className={cn('font-medium', sizeStyles.label, labelClassName)}>
                {label}
              </div>
            )}
            <div className={cn('mt-1', fullWidth && 'w-full')}>
              {field}
            </div>
          </div>
        );
      });

      return (
        <div className={cn('flex flex-col', gapClass, fullWidth && 'w-full')}>
          {fieldItems}
          {actions && (
            <div className={cn('flex items-center gap-3 mt-2', actionClassName)}>
              {actions}
            </div>
          )}
        </div>
      );
    };

    // ========================================================================
    // RENDU DU LAYOUT COLONNES
    // ========================================================================

    const renderColumns = () => {
      const totalFields = fields.length;
      const half = Math.ceil(totalFields / 2);

      const leftFields = fields.slice(0, half);
      const rightFields = fields.slice(half);

      return (
        <div className={cn('grid grid-cols-1 md:grid-cols-2', gapClass, fullWidth && 'w-full')}>
          <div className={cn('flex flex-col', gapClass)}>
            {leftFields.map((field, index) => (
              <div key={index} className={cn('flex flex-col', fieldClassName)}>
                {field}
              </div>
            ))}
          </div>
          <div className={cn('flex flex-col', gapClass)}>
            {rightFields.map((field, index) => (
              <div key={index} className={cn('flex flex-col', fieldClassName)}>
                {field}
              </div>
            ))}
          </div>
          {actions && (
            <div className={cn('col-span-2 flex items-center gap-3', actionClassName)}>
              {actions}
            </div>
          )}
        </div>
      );
    };

    // ========================================================================
    // RENDU DU LAYOUT AVEC COLONNES PERSONNALISÉES
    // ========================================================================

    const renderCustomColumns = () => {
      // Si columnRatio est une chaîne, la parser
      const ratios = columnRatio.split(' ').map((r) => {
        if (r.includes('fr')) {
          return r;
        }
        return `${r}px`;
      });

      const style = {
        gridTemplateColumns: ratios.join(' '),
      };

      return (
        <div
          className={cn(
            'grid',
            gapClass,
            fullWidth && 'w-full',
            alignClass,
            justifyClass
          )}
          style={style}
        >
          {fields.map((field, index) => (
            <div key={index} className={cn('flex flex-col', fieldClassName)}>
              {field}
            </div>
          ))}
          {actions && (
            <div className={cn('col-span-full flex items-center gap-3', actionClassName)}>
              {actions}
            </div>
          )}
        </div>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const containerClasses = cn(
      'relative',
      !noPadding && sizeStyles.padding,
      !noBorder && 'border border-gray-200 dark:border-gray-700',
      !noBackground && 'bg-white dark:bg-gray-900',
      'rounded-xl',
      containerClassName
    );

    // Déterminer le rendu en fonction de la variante
    let content = null;

    switch (variant) {
      case 'horizontal':
        content = renderHorizontal();
        break;
      case 'grid':
        content = renderGrid();
        break;
      case 'inline':
        content = renderInline();
        break;
      case 'stacked':
        content = renderStacked();
        break;
      case 'columns':
        content = renderColumns();
        break;
      default:
        content = renderVertical();
        break;
    }

    // Si variant est 'columns' et columnRatio est personnalisé
    if (isColumns && columnRatio && columnRatio !== '1fr 1fr') {
      content = renderCustomColumns();
    }

    if (debug) {
      console.group('🔍 FormLayout Debug');
      console.log('Variant:', variant);
      console.log('Size:', size);
      console.log('Gap:', gap);
      console.log('Columns:', columns);
      console.log('Fields:', fields.length);
      console.log('Labels:', labels.length);
      console.groupEnd();
    }

    return (
      <div
        ref={ref}
        id={id}
        className={cn(
          containerClasses,
          className
        )}
        aria-label={ariaLabel}
        role="form"
      >
        {content}
      </div>
    );
  }
);

FormLayout.displayName = 'FormLayout';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- FormLayout.Field ---
interface FormFieldProps {
  children: ReactNode;
  label?: ReactNode;
  className?: string;
  labelClassName?: string;
  required?: boolean;
  error?: string;
}

export const FormField: React.FC<FormFieldProps> = ({
  children,
  label,
  className,
  labelClassName,
  required = false,
  error,
}) => {
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {label && (
        <label className={cn(
          'text-sm font-medium text-gray-700 dark:text-gray-300',
          labelClassName
        )}>
          {label}
          {required && <span className="ml-1 text-red-500">*</span>}
        </label>
      )}
      {children}
      {error && (
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      )}
    </div>
  );
};

// --- FormLayout.Actions ---
interface FormActionsProps {
  children: ReactNode;
  className?: string;
  alignment?: 'left' | 'center' | 'right' | 'between';
}

export const FormActions: React.FC<FormActionsProps> = ({
  children,
  className,
  alignment = 'right',
}) => {
  const alignMap = {
    left: 'justify-start',
    center: 'justify-center',
    right: 'justify-end',
    between: 'justify-between',
  };

  return (
    <div className={cn(
      'flex items-center gap-3',
      alignMap[alignment],
      className
    )}>
      {children}
    </div>
  );
};

// --- FormLayout.Group ---
interface FormGroupProps {
  children: ReactNode;
  title?: ReactNode;
  description?: ReactNode;
  className?: string;
  titleClassName?: string;
  descriptionClassName?: string;
}

export const FormGroup: React.FC<FormGroupProps> = ({
  children,
  title,
  description,
  className,
  titleClassName,
  descriptionClassName,
}) => {
  return (
    <div className={cn('space-y-3', className)}>
      {(title || description) && (
        <div>
          {title && (
            <h3 className={cn('font-medium text-gray-900 dark:text-white', titleClassName)}>
              {title}
            </h3>
          )}
          {description && (
            <p className={cn('text-sm text-gray-500 dark:text-gray-400', descriptionClassName)}>
              {description}
            </p>
          )}
        </div>
      )}
      <div className="space-y-4">
        {children}
      </div>
    </div>
  );
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(FormLayout, {
  Field: FormField,
  Actions: FormActions,
  Group: FormGroup,
});

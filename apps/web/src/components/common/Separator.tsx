// apps/web/src/components/common/Separator.tsx
'use client';

import React, {
  ReactNode,
  forwardRef,
  Ref,
  useMemo,
  useId,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, MotionProps } from 'framer-motion';

// ============================================================================
// TYPES
// ============================================================================

export type SeparatorOrientation = 'horizontal' | 'vertical';
export type SeparatorVariant = 
  | 'solid' 
  | 'dashed' 
  | 'dotted' 
  | 'double' 
  | 'groove' 
  | 'ridge' 
  | 'inset' 
  | 'outset'
  | 'gradient'
  | 'glow'
  | 'rainbow';
export type SeparatorSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type SeparatorColor = 
  | 'default' 
  | 'primary' 
  | 'success' 
  | 'warning' 
  | 'danger' 
  | 'info' 
  | 'brand'
  | 'gray'
  | 'white'
  | 'black';
export type SeparatorAlignment = 'center' | 'left' | 'right' | 'start' | 'end';
export type SeparatorLabelPosition = 'inline' | 'above' | 'below' | 'inside';

export interface SeparatorProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children'> {
  /** Orientation du séparateur */
  orientation?: SeparatorOrientation;
  /** Variante visuelle */
  variant?: SeparatorVariant;
  /** Taille/épaisseur */
  size?: SeparatorSize;
  /** Couleur */
  color?: SeparatorColor;
  /** Alignement du label */
  labelAlignment?: SeparatorAlignment;
  /** Position du label */
  labelPosition?: SeparatorLabelPosition;
  /** Label à afficher */
  label?: ReactNode;
  /** Classes additionnelles */
  className?: string;
  /** Classes pour le label */
  labelClassName?: string;
  /** Classes pour la ligne */
  lineClassName?: string;
  /** Épaisseur personnalisée */
  thickness?: number | string;
  /** Longueur personnalisée */
  length?: number | string;
  /** Espacement personnalisé */
  spacing?: number | string;
  /** Opacité */
  opacity?: number;
  /** Désactiver les animations */
  disableAnimation?: boolean;
  /** Animation à l'apparition */
  animateOnMount?: boolean;
  /** ID */
  id?: string;
  /** Rôle ARIA */
  role?: string;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const SIZE_MAP: Record<SeparatorSize, { thickness: string; gap: string; fontSize: string }> = {
  xs: { thickness: 'h-px', gap: 'gap-1', fontSize: 'text-[10px]' },
  sm: { thickness: 'h-0.5', gap: 'gap-2', fontSize: 'text-xs' },
  md: { thickness: 'h-1', gap: 'gap-3', fontSize: 'text-sm' },
  lg: { thickness: 'h-1.5', gap: 'gap-4', fontSize: 'text-base' },
  xl: { thickness: 'h-2', gap: 'gap-5', fontSize: 'text-lg' },
};

const COLOR_MAP: Record<SeparatorColor, string> = {
  default: 'bg-gray-200 dark:bg-gray-700',
  primary: 'bg-brand-500 dark:bg-brand-400',
  success: 'bg-green-500 dark:bg-green-400',
  warning: 'bg-yellow-500 dark:bg-yellow-400',
  danger: 'bg-red-500 dark:bg-red-400',
  info: 'bg-blue-500 dark:bg-blue-400',
  brand: 'bg-brand-500 dark:bg-brand-400',
  gray: 'bg-gray-300 dark:bg-gray-600',
  white: 'bg-white',
  black: 'bg-black',
};

const VARIANT_STYLES: Record<SeparatorVariant, { borderStyle: string; borderWidth: string }> = {
  solid: { borderStyle: 'solid', borderWidth: 'border' },
  dashed: { borderStyle: 'dashed', borderWidth: 'border-2' },
  dotted: { borderStyle: 'dotted', borderWidth: 'border-2' },
  double: { borderStyle: 'double', borderWidth: 'border-4' },
  groove: { borderStyle: 'groove', borderWidth: 'border-2' },
  ridge: { borderStyle: 'ridge', borderWidth: 'border-2' },
  inset: { borderStyle: 'inset', borderWidth: 'border-2' },
  outset: { borderStyle: 'outset', borderWidth: 'border-2' },
  gradient: { borderStyle: 'solid', borderWidth: 'border' },
  glow: { borderStyle: 'solid', borderWidth: 'border' },
  rainbow: { borderStyle: 'solid', borderWidth: 'border' },
};

const LABEL_ALIGNMENT_MAP: Record<SeparatorAlignment, string> = {
  center: 'justify-center',
  left: 'justify-start',
  right: 'justify-end',
  start: 'justify-start',
  end: 'justify-end',
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const Separator = forwardRef<HTMLDivElement, SeparatorProps>(
  (props, ref) => {
    const {
      // Orientation
      orientation = 'horizontal',
      
      // Apparence
      variant = 'solid',
      size = 'md',
      color = 'default',
      
      // Label
      label,
      labelAlignment = 'center',
      labelPosition = 'inline',
      
      // Classes
      className,
      labelClassName,
      lineClassName,
      
      // Personnalisation
      thickness,
      length,
      spacing,
      opacity = 1,
      
      // Animation
      disableAnimation = false,
      animateOnMount = false,
      
      // Accessibilité
      id,
      role = 'separator',
      
      // Autres
      ...rest
    } = props;

    // ========================================================================
    // ID
    // ========================================================================

    const uniqueId = useId();
    const separatorId = id || `nexus-separator-${uniqueId}`;

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const isHorizontal = orientation === 'horizontal';
    const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
    const colorStyles = COLOR_MAP[color] || COLOR_MAP.default;
    const variantStyles = VARIANT_STYLES[variant] || VARIANT_STYLES.solid;
    const alignmentStyles = LABEL_ALIGNMENT_MAP[labelAlignment] || LABEL_ALIGNMENT_MAP.center;

    const hasLabel = label !== undefined && label !== null && label !== '';
    const isInline = labelPosition === 'inline';
    const isAbove = labelPosition === 'above';
    const isBelow = labelPosition === 'below';
    const isInside = labelPosition === 'inside';

    // ========================================================================
    // STYLES
    // ========================================================================

    const containerStyles: React.CSSProperties = {
      opacity,
      ...(spacing && {
        [isHorizontal ? 'padding' : 'margin']: 
          typeof spacing === 'number' ? `${spacing}px` : spacing,
      }),
    };

    const lineStyles: React.CSSProperties = {
      ...(thickness && {
        [isHorizontal ? 'height' : 'width']: 
          typeof thickness === 'number' ? `${thickness}px` : thickness,
      }),
      ...(length && {
        [isHorizontal ? 'width' : 'height']: 
          typeof length === 'number' ? `${length}px` : length,
      }),
    };

    // ========================================================================
    // VARIANTES SPÉCIALES
    // ========================================================================

    const getVariantClasses = () => {
      const baseClasses = 'flex-1';

      switch (variant) {
        case 'gradient':
          return cn(
            baseClasses,
            isHorizontal 
              ? 'h-0.5 bg-gradient-to-r from-transparent via-brand-500 to-transparent'
              : 'w-0.5 bg-gradient-to-b from-transparent via-brand-500 to-transparent'
          );
        
        case 'glow':
          return cn(
            baseClasses,
            isHorizontal 
              ? 'h-0.5 bg-brand-500 shadow-[0_0_15px_rgba(99,102,241,0.5)]'
              : 'w-0.5 bg-brand-500 shadow-[0_0_15px_rgba(99,102,241,0.5)]'
          );
        
        case 'rainbow':
          return cn(
            baseClasses,
            isHorizontal 
              ? 'h-1 bg-gradient-to-r from-red-500 via-yellow-500 via-green-500 via-blue-500 to-purple-500'
              : 'w-1 bg-gradient-to-b from-red-500 via-yellow-500 via-green-500 via-blue-500 to-purple-500'
          );
        
        default:
          return cn(
            baseClasses,
            sizeStyles.thickness,
            colorStyles,
            variantStyles.borderStyle === 'solid' ? '' : `border-${variantStyles.borderStyle}`,
            variantStyles.borderWidth,
            color === 'default' ? 'border-gray-200 dark:border-gray-700' : `border-${color}-500`,
            lineClassName
          );
      }
    };

    // ========================================================================
    // RENDU DE LA LIGNE
    // ========================================================================

    const renderLine = (withAnimation: boolean = false) => {
      const lineElement = (
        <div
          className={getVariantClasses()}
          style={lineStyles}
          aria-hidden="true"
        />
      );

      if (withAnimation && animateOnMount && !disableAnimation) {
        return (
          <motion.div
            initial={{ scaleX: 0, scaleY: 0 }}
            animate={{ scaleX: 1, scaleY: 1 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className="flex-1"
          >
            {lineElement}
          </motion.div>
        );
      }

      return lineElement;
    };

    // ========================================================================
    // RENDU DU LABEL
    // ========================================================================

    const renderLabel = (position: 'inline' | 'above' | 'below') => {
      if (!hasLabel) return null;

      const labelElement = (
        <span
          className={cn(
            'whitespace-nowrap font-medium text-gray-500 dark:text-gray-400',
            sizeStyles.fontSize,
            color === 'default' ? 'text-gray-500 dark:text-gray-400' : `text-${color}-600 dark:text-${color}-400`,
            labelClassName
          )}
        >
          {label}
        </span>
      );

      if (position === 'above') {
        return (
          <div className="flex justify-center w-full mb-2">
            {labelElement}
          </div>
        );
      }

      if (position === 'below') {
        return (
          <div className="flex justify-center w-full mt-2">
            {labelElement}
          </div>
        );
      }

      if (position === 'inside') {
        return (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className={cn(
              'px-3 py-0.5 rounded-full bg-white dark:bg-gray-900 text-xs font-medium',
              color === 'default' ? 'text-gray-500 dark:text-gray-400' : `text-${color}-600 dark:text-${color}-400`,
              labelClassName
            )}>
              {label}
            </span>
          </div>
        );
      }

      return labelElement;
    };

    // ========================================================================
    // RENDU DU SÉPARATEUR EN LIGNE (avec label)
    // ========================================================================

    const renderInlineSeparator = () => {
      const lineWithAnimation = renderLine(true);

      return (
        <div
          className={cn(
            'flex items-center w-full',
            sizeStyles.gap,
            alignmentStyles,
            className
          )}
          style={containerStyles}
        >
          {labelAlignment === 'left' || labelAlignment === 'start' ? (
            <>
              {renderLabel('inline')}
              {lineWithAnimation}
            </>
          ) : labelAlignment === 'right' || labelAlignment === 'end' ? (
            <>
              {lineWithAnimation}
              {renderLabel('inline')}
            </>
          ) : (
            <>
              {lineWithAnimation}
              {renderLabel('inline')}
              {lineWithAnimation}
            </>
          )}
        </div>
      );
    };

    // ========================================================================
    // RENDU DU SÉPARATEUR SIMPLE (sans label)
    // ========================================================================

    const renderSimpleSeparator = () => {
      const lineWithAnimation = renderLine(true);

      if (isHorizontal) {
        return (
          <div
            ref={ref}
            id={separatorId}
            className={cn(
              'flex w-full',
              alignmentStyles,
              className
            )}
            style={containerStyles}
            role={role}
            aria-orientation="horizontal"
            {...rest}
          >
            {lineWithAnimation}
          </div>
        );
      }

      return (
        <div
          ref={ref}
          id={separatorId}
          className={cn(
            'flex h-full flex-col',
            alignmentStyles,
            className
          )}
          style={containerStyles}
          role={role}
          aria-orientation="vertical"
          {...rest}
        >
          {lineWithAnimation}
        </div>
      );
    };

    // ========================================================================
    // RENDU DU SÉPARATEUR AVEC LABEL (au-dessus ou en-dessous)
    // ========================================================================

    const renderLabeledSeparator = () => {
      if (isAbove) {
        return (
          <div
            ref={ref}
            id={separatorId}
            className={cn(
              'flex flex-col items-center w-full',
              className
            )}
            style={containerStyles}
            role={role}
            {...rest}
          >
            {renderLabel('above')}
            {renderSimpleSeparator()}
          </div>
        );
      }

      if (isBelow) {
        return (
          <div
            ref={ref}
            id={separatorId}
            className={cn(
              'flex flex-col items-center w-full',
              className
            )}
            style={containerStyles}
            role={role}
            {...rest}
          >
            {renderSimpleSeparator()}
            {renderLabel('below')}
          </div>
        );
      }

      if (isInside) {
        return (
          <div
            ref={ref}
            id={separatorId}
            className={cn(
              'relative flex items-center w-full',
              className
            )}
            style={containerStyles}
            role={role}
            {...rest}
          >
            {renderSimpleSeparator()}
            {renderLabel('inside')}
          </div>
        );
      }

      return renderSimpleSeparator();
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    // Déterminer le rendu approprié
    let renderContent;

    if (hasLabel && isInline) {
      renderContent = renderInlineSeparator();
    } else if (hasLabel && (isAbove || isBelow || isInside)) {
      renderContent = renderLabeledSeparator();
    } else {
      renderContent = renderSimpleSeparator();
    }

    // Animation d'apparition
    if (animateOnMount && !disableAnimation) {
      return (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3 }}
          className="w-full"
        >
          {renderContent}
        </motion.div>
      );
    }

    return renderContent;
  }
);

Separator.displayName = 'Separator';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- Separator.WithLabel ---
interface SeparatorWithLabelProps extends Omit<SeparatorProps, 'label'> {
  label: ReactNode;
}

export const SeparatorWithLabel: React.FC<SeparatorWithLabelProps> = ({
  label,
  labelPosition = 'inline',
  labelAlignment = 'center',
  ...props
}) => {
  return (
    <Separator
      {...props}
      label={label}
      labelPosition={labelPosition}
      labelAlignment={labelAlignment}
    />
  );
};

// --- Separator.Vertical ---
interface SeparatorVerticalProps extends Omit<SeparatorProps, 'orientation'> {}

export const SeparatorVertical: React.FC<SeparatorVerticalProps> = ({
  size = 'md',
  className,
  ...props
}) => {
  return (
    <Separator
      {...props}
      orientation="vertical"
      size={size}
      className={cn('h-full min-h-[20px]', className)}
    />
  );
};

// --- Separator.Horizontal ---
interface SeparatorHorizontalProps extends Omit<SeparatorProps, 'orientation'> {}

export const SeparatorHorizontal: React.FC<SeparatorHorizontalProps> = ({
  className,
  ...props
}) => {
  return (
    <Separator
      {...props}
      orientation="horizontal"
      className={cn('w-full', className)}
    />
  );
};

// ============================================================================
// HOOKS
// ============================================================================

export const useSeparator = (options?: {
  orientation?: SeparatorOrientation;
  variant?: SeparatorVariant;
  color?: SeparatorColor;
}) => {
  const [isVisible, setIsVisible] = React.useState(true);

  const toggle = React.useCallback(() => {
    setIsVisible((prev) => !prev);
  }, []);

  const show = React.useCallback(() => {
    setIsVisible(true);
  }, []);

  const hide = React.useCallback(() => {
    setIsVisible(false);
  }, []);

  return {
    isVisible,
    toggle,
    show,
    hide,
    props: {
      orientation: options?.orientation || 'horizontal',
      variant: options?.variant || 'solid',
      color: options?.color || 'default',
    },
  };
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(Separator, {
  WithLabel: SeparatorWithLabel,
  Vertical: SeparatorVertical,
  Horizontal: SeparatorHorizontal,
});

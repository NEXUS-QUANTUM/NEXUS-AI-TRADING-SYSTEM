/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import * as CheckboxPrimitive from '@radix-ui/react-checkbox';
import { cn } from '@/utils/helpers';
import { Check, Minus } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface CheckboxProps
  extends React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root> {
  label?: string;
  description?: string;
  error?: string;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'outline' | 'filled' | 'glass';
  indeterminate?: boolean;
  labelPosition?: 'left' | 'right';
  asChild?: boolean;
}

// ============================================
// COMPOSANT
// ============================================

const Checkbox = React.forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  CheckboxProps
>(
  (
    {
      className,
      checked,
      defaultChecked,
      onCheckedChange,
      disabled,
      required,
      name,
      value,
      id,
      label,
      description,
      error,
      size = 'md',
      variant = 'default',
      indeterminate = false,
      labelPosition = 'right',
      asChild,
      ...props
    },
    ref
  ) => {
    // ============================================
    // RÉFÉRENCES
    // ============================================
    const innerRef = React.useRef<HTMLButtonElement>(null);

    // ============================================
    // ÉTATS
    // ============================================
    const [isChecked, setIsChecked] = React.useState(
      checked || defaultChecked || false
    );
    const [isIndeterminate, setIsIndeterminate] = React.useState(indeterminate);

    // ============================================
    // EFFETS
    // ============================================
    React.useEffect(() => {
      if (checked !== undefined) {
        setIsChecked(checked);
      }
    }, [checked]);

    React.useEffect(() => {
      setIsIndeterminate(indeterminate);
    }, [indeterminate]);

    React.useEffect(() => {
      if (innerRef.current) {
        const input = innerRef.current as any;
        if (input.indeterminate !== undefined) {
          input.indeterminate = isIndeterminate;
        }
      }
    }, [isIndeterminate]);

    // ============================================
    // FONCTIONS
    // ============================================

    const handleCheckedChange = (newChecked: boolean) => {
      setIsChecked(newChecked);
      onCheckedChange?.(newChecked);
    };

    // ============================================
    // VARIANTES
    // ============================================

    const sizeClasses = {
      sm: 'h-3.5 w-3.5',
      md: 'h-4 w-4',
      lg: 'h-5 w-5',
    };

    const iconSizeClasses = {
      sm: 'h-2.5 w-2.5',
      md: 'h-3 w-3',
      lg: 'h-4 w-4',
    };

    const variantClasses = {
      default: 'border-gray-300 dark:border-gray-600 data-[state=checked]:bg-blue-600 data-[state=checked]:border-blue-600',
      outline: 'border-2 border-gray-300 dark:border-gray-600 data-[state=checked]:bg-transparent data-[state=checked]:border-blue-600 data-[state=checked]:text-blue-600',
      filled: 'bg-gray-100 dark:bg-gray-800 border-transparent data-[state=checked]:bg-blue-600 data-[state=checked]:text-white',
      glass: 'bg-white/10 backdrop-blur-sm border border-white/20 data-[state=checked]:bg-blue-600/80 data-[state=checked]:border-blue-400',
    };

    const labelSizeClasses = {
      sm: 'text-xs',
      md: 'text-sm',
      lg: 'text-base',
    };

    // ============================================
    // RENDU
    // ============================================

    const checkboxId = id || `checkbox-${React.useId()}`;

    const checkboxElement = (
      <CheckboxPrimitive.Root
        ref={ref}
        id={checkboxId}
        name={name}
        value={value}
        checked={isChecked}
        defaultChecked={defaultChecked}
        onCheckedChange={handleCheckedChange}
        disabled={disabled}
        required={required}
        className={cn(
          'peer shrink-0 rounded transition-all duration-200',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2',
          'disabled:cursor-not-allowed disabled:opacity-50',
          sizeClasses[size],
          variantClasses[variant],
          isIndeterminate && 'data-[state=checked]:bg-blue-600 data-[state=checked]:border-blue-600',
          error && 'border-red-500 ring-1 ring-red-500',
          className
        )}
        {...props}
      >
        <CheckboxPrimitive.Indicator
          className={cn('flex items-center justify-center text-current')}
        >
          {isIndeterminate ? (
            <Minus className={cn('text-white dark:text-white', iconSizeClasses[size])} />
          ) : (
            <Check className={cn('text-white dark:text-white', iconSizeClasses[size])} />
          )}
        </CheckboxPrimitive.Indicator>
      </CheckboxPrimitive.Root>
    );

    // Si pas de label, retourner uniquement la checkbox
    if (!label && !description) {
      return checkboxElement;
    }

    // Layout avec label
    return (
      <div className="flex items-start gap-2">
        {labelPosition === 'left' && (
          <div className="flex flex-col items-end">
            {label && (
              <label
                htmlFor={checkboxId}
                className={cn(
                  'font-medium text-gray-700 dark:text-gray-300 cursor-pointer select-none',
                  labelSizeClasses[size],
                  disabled && 'cursor-not-allowed opacity-50'
                )}
              >
                {label}
              </label>
            )}
            {description && (
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {description}
              </p>
            )}
          </div>
        )}

        <div className="flex items-center gap-2">
          {checkboxElement}
          {labelPosition === 'right' && (
            <div className="flex flex-col">
              {label && (
                <label
                  htmlFor={checkboxId}
                  className={cn(
                    'font-medium text-gray-700 dark:text-gray-300 cursor-pointer select-none',
                    labelSizeClasses[size],
                    disabled && 'cursor-not-allowed opacity-50'
                  )}
                >
                  {label}
                </label>
              )}
              {description && (
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {description}
                </p>
              )}
            </div>
          )}
        </div>

        {error && (
          <p className="text-xs text-red-500 mt-1">{error}</p>
        )}
      </div>
    );
  }
);
Checkbox.displayName = CheckboxPrimitive.Root.displayName;

// ============================================
// SOUS-COMPOSANTS
// ============================================

export interface CheckboxGroupProps
  extends React.HTMLAttributes<HTMLDivElement> {
  value?: string[];
  defaultValue?: string[];
  onValueChange?: (value: string[]) => void;
  orientation?: 'horizontal' | 'vertical';
  disabled?: boolean;
  name?: string;
  children: React.ReactNode;
}

const CheckboxGroup = React.forwardRef<HTMLDivElement, CheckboxGroupProps>(
  (
    {
      value,
      defaultValue = [],
      onValueChange,
      orientation = 'vertical',
      disabled = false,
      name,
      className,
      children,
      ...props
    },
    ref
  ) => {
    const [selectedValues, setSelectedValues] = React.useState<string[]>(
      value || defaultValue
    );

    React.useEffect(() => {
      if (value !== undefined) {
        setSelectedValues(value);
      }
    }, [value]);

    const handleCheckboxChange = (checkboxValue: string, checked: boolean) => {
      const newValues = checked
        ? [...selectedValues, checkboxValue]
        : selectedValues.filter((v) => v !== checkboxValue);

      setSelectedValues(newValues);
      onValueChange?.(newValues);
    };

    const childrenWithProps = React.Children.map(children, (child) => {
      if (React.isValidElement(child) && child.type === Checkbox) {
        const childProps = child.props as CheckboxProps;
        const checkboxValue = childProps.value as string;

        return React.cloneElement(child as React.ReactElement, {
          checked: selectedValues.includes(checkboxValue),
          onCheckedChange: (checked: boolean) =>
            handleCheckboxChange(checkboxValue, checked),
          disabled: disabled || childProps.disabled,
          name: name || childProps.name,
        });
      }
      return child;
    });

    return (
      <div
        ref={ref}
        className={cn(
          'flex gap-2',
          orientation === 'horizontal' ? 'flex-row flex-wrap' : 'flex-col',
          className
        )}
        {...props}
      >
        {childrenWithProps}
      </div>
    );
  }
);
CheckboxGroup.displayName = 'CheckboxGroup';

// ============================================
// EXPORTATIONS
// ============================================

export { Checkbox, CheckboxGroup };

export default Checkbox;

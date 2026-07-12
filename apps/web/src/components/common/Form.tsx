/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import * as LabelPrimitive from '@radix-ui/react-label';
import { Slot } from '@radix-ui/react-slot';
import { cn } from '@/utils/helpers';
import { Label } from './Label';
import { AlertCircle, CheckCircle, Info, AlertTriangle } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface FormProps extends React.FormHTMLAttributes<HTMLFormElement> {
  asChild?: boolean;
}

export interface FormItemProps extends React.HTMLAttributes<HTMLDivElement> {
  asChild?: boolean;
  error?: string;
  success?: string;
  warning?: string;
  info?: string;
  required?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
}

export interface FormLabelProps
  extends React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root> {
  required?: boolean;
  optional?: boolean;
  tooltip?: string;
}

export interface FormControlProps extends React.HTMLAttributes<HTMLDivElement> {
  asChild?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
  required?: boolean;
}

export interface FormDescriptionProps
  extends React.HTMLAttributes<HTMLParagraphElement> {
  asChild?: boolean;
}

export interface FormMessageProps
  extends React.HTMLAttributes<HTMLParagraphElement> {
  asChild?: boolean;
  variant?: 'default' | 'error' | 'success' | 'warning' | 'info';
}

export interface FormFieldProps {
  name: string;
  children: React.ReactNode;
  error?: string;
  success?: string;
  warning?: string;
  info?: string;
  required?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
}

export interface FormFieldContextType {
  id: string;
  name: string;
  error?: string;
  success?: string;
  warning?: string;
  info?: string;
  required?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
  isInvalid?: boolean;
  isSuccess?: boolean;
  isWarning?: boolean;
  isInfo?: boolean;
  describedBy?: string;
}

// ============================================
// CONTEXTES
// ============================================

const FormFieldContext = React.createContext<FormFieldContextType | undefined>(
  undefined
);

const useFormField = () => {
  const context = React.useContext(FormFieldContext);
  if (!context) {
    throw new Error('useFormField must be used within a FormField');
  }
  return context;
};

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

const Form = React.forwardRef<HTMLFormElement, FormProps>(
  ({ className, asChild, children, ...props }, ref) => {
    const Comp = asChild ? Slot : 'form';
    return (
      <Comp ref={ref} className={cn('space-y-6', className)} {...props}>
        {children}
      </Comp>
    );
  }
);
Form.displayName = 'Form';

// ============================================
// FORM ITEM
// ============================================

const FormItem = React.forwardRef<HTMLDivElement, FormItemProps>(
  (
    {
      className,
      asChild,
      error,
      success,
      warning,
      info,
      required,
      disabled,
      readOnly,
      children,
      ...props
    },
    ref
  ) => {
    const id = React.useId();
    const [isInvalid, setIsInvalid] = React.useState(!!error);
    const [isSuccess, setIsSuccess] = React.useState(!!success);
    const [isWarning, setIsWarning] = React.useState(!!warning);
    const [isInfo, setIsInfo] = React.useState(!!info);

    React.useEffect(() => {
      setIsInvalid(!!error);
      setIsSuccess(!!success);
      setIsWarning(!!warning);
      setIsInfo(!!info);
    }, [error, success, warning, info]);

    const describedBy = React.useMemo(() => {
      const ids = [];
      if (error) ids.push(`${id}-error`);
      if (success) ids.push(`${id}-success`);
      if (warning) ids.push(`${id}-warning`);
      if (info) ids.push(`${id}-info`);
      if (props['aria-describedby']) ids.push(props['aria-describedby']);
      return ids.join(' ') || undefined;
    }, [id, error, success, warning, info, props]);

    const contextValue: FormFieldContextType = {
      id,
      name: props.id || id,
      error,
      success,
      warning,
      info,
      required,
      disabled,
      readOnly,
      isInvalid,
      isSuccess,
      isWarning,
      isInfo,
      describedBy,
    };

    const Comp = asChild ? Slot : 'div';

    return (
      <FormFieldContext.Provider value={contextValue}>
        <Comp
          ref={ref}
          className={cn(
            'space-y-2',
            isInvalid && 'text-red-500',
            isSuccess && 'text-green-500',
            isWarning && 'text-yellow-500',
            isInfo && 'text-blue-500',
            className
          )}
          {...props}
        >
          {children}
        </Comp>
      </FormFieldContext.Provider>
    );
  }
);
FormItem.displayName = 'FormItem';

// ============================================
// FORM LABEL
// ============================================

const FormLabel = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  FormLabelProps
>(({ className, required, optional, tooltip, children, ...props }, ref) => {
  const context = useFormField();
  const isRequired = required !== undefined ? required : context?.required;

  return (
    <Label
      ref={ref}
      className={cn(
        'text-sm font-medium',
        context?.isInvalid && 'text-red-500',
        context?.isSuccess && 'text-green-500',
        context?.isWarning && 'text-yellow-500',
        context?.isInfo && 'text-blue-500',
        className
      )}
      htmlFor={context?.id}
      {...props}
    >
      {children}
      {isRequired && (
        <span className="ml-0.5 text-red-500" aria-hidden="true">
          *
        </span>
      )}
      {optional && (
        <span className="ml-1 text-xs text-gray-400 dark:text-gray-500">
          (optionnel)
        </span>
      )}
      {tooltip && (
        <span className="ml-1 cursor-help text-gray-400 dark:text-gray-500">
          ⓘ
        </span>
      )}
    </Label>
  );
});
FormLabel.displayName = 'FormLabel';

// ============================================
// FORM CONTROL
// ============================================

const FormControl = React.forwardRef<HTMLDivElement, FormControlProps>(
  ({ className, asChild, children, ...props }, ref) => {
    const context = useFormField();

    const childProps = {
      id: context.id,
      'aria-describedby': context.describedBy,
      'aria-invalid': context.isInvalid,
      'aria-required': context.required,
      'aria-disabled': context.disabled,
      'aria-readonly': context.readOnly,
      disabled: context.disabled,
      readOnly: context.readOnly,
      required: context.required,
    };

    const Comp = asChild ? Slot : 'div';

    return (
      <Comp
        ref={ref}
        className={cn(
          'relative',
          context?.isInvalid && 'ring-1 ring-red-500 rounded-md',
          context?.isSuccess && 'ring-1 ring-green-500 rounded-md',
          context?.isWarning && 'ring-1 ring-yellow-500 rounded-md',
          context?.isInfo && 'ring-1 ring-blue-500 rounded-md',
          className
        )}
        {...props}
      >
        {React.Children.map(children, (child) => {
          if (React.isValidElement(child)) {
            return React.cloneElement(child, childProps);
          }
          return child;
        })}
      </Comp>
    );
  }
);
FormControl.displayName = 'FormControl';

// ============================================
// FORM DESCRIPTION
// ============================================

const FormDescription = React.forwardRef<
  HTMLParagraphElement,
  FormDescriptionProps
>(({ className, asChild, children, ...props }, ref) => {
  const context = useFormField();
  const id = context ? `${context.id}-description` : undefined;

  const Comp = asChild ? Slot : 'p';

  return (
    <Comp
      ref={ref}
      id={id}
      className={cn(
        'text-sm text-gray-500 dark:text-gray-400',
        context?.isInvalid && 'text-red-500',
        context?.isSuccess && 'text-green-500',
        context?.isWarning && 'text-yellow-500',
        context?.isInfo && 'text-blue-500',
        className
      )}
      {...props}
    >
      {children}
    </Comp>
  );
});
FormDescription.displayName = 'FormDescription';

// ============================================
// FORM MESSAGE
// ============================================

const FormMessage = React.forwardRef<HTMLParagraphElement, FormMessageProps>(
  ({ className, asChild, variant = 'default', children, ...props }, ref) => {
    const context = useFormField();

    // Utiliser l'erreur du contexte si disponible
    const message = context?.error || context?.success || context?.warning || context?.info || children;
    const currentVariant = context?.error ? 'error' :
                          context?.success ? 'success' :
                          context?.warning ? 'warning' :
                          context?.info ? 'info' :
                          variant;

    if (!message) return null;

    const variantClasses = {
      default: 'text-gray-500 dark:text-gray-400',
      error: 'text-red-500',
      success: 'text-green-500',
      warning: 'text-yellow-500',
      info: 'text-blue-500',
    };

    const iconMap = {
      error: AlertCircle,
      success: CheckCircle,
      warning: AlertTriangle,
      info: Info,
      default: Info,
    };

    const Icon = iconMap[currentVariant as keyof typeof iconMap] || Info;

    const id = context ? `${context.id}-${currentVariant}` : undefined;

    const Comp = asChild ? Slot : 'p';

    return (
      <Comp
        ref={ref}
        id={id}
        className={cn(
          'flex items-center gap-1.5 text-sm',
          variantClasses[currentVariant as keyof typeof variantClasses],
          className
        )}
        {...props}
      >
        <Icon className="h-4 w-4 flex-shrink-0" />
        {message}
      </Comp>
    );
  }
);
FormMessage.displayName = 'FormMessage';

// ============================================
// FORM FIELD
// ============================================

const FormField = React.forwardRef<HTMLDivElement, FormFieldProps>(
  ({ name, children, error, success, warning, info, required, disabled, readOnly, ...props }, ref) => {
    const id = React.useId();

    const contextValue: FormFieldContextType = {
      id: `${id}-${name}`,
      name,
      error,
      success,
      warning,
      info,
      required,
      disabled,
      readOnly,
      isInvalid: !!error,
      isSuccess: !!success,
      isWarning: !!warning,
      isInfo: !!info,
      describedBy: [
        error && `${id}-${name}-error`,
        success && `${id}-${name}-success`,
        warning && `${id}-${name}-warning`,
        info && `${id}-${name}-info`,
      ]
        .filter(Boolean)
        .join(' ') || undefined,
    };

    return (
      <FormFieldContext.Provider value={contextValue}>
        <div ref={ref} {...props}>
          {children}
        </div>
      </FormFieldContext.Provider>
    );
  }
);
FormField.displayName = 'FormField';

// ============================================
// EXPORTATIONS
// ============================================

export {
  Form,
  FormItem,
  FormLabel,
  FormControl,
  FormDescription,
  FormMessage,
  FormField,
  useFormField,
};

export default Form;

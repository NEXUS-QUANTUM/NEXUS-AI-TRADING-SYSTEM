// apps/web/src/components/common/Modal.tsx
'use client';

import React, {
  Fragment,
  ReactNode,
  useEffect,
  useRef,
  useState,
  useCallback,
  useMemo,
  forwardRef,
  Ref,
  createContext,
  useContext,
  useId,
  Children,
  isValidElement,
  cloneElement,
} from 'react';
import { Dialog, Transition, TransitionChild } from '@headlessui/react';
import {
  XMarkIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  InformationCircleIcon,
  ExclamationCircleIcon,
  QuestionMarkCircleIcon,
  ArrowPathIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

// ============================================================================
// CONTEXT
// ============================================================================

interface ModalContextType {
  isOpen: boolean;
  onClose: () => void;
  size: ModalSize;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  registerStep: (id: string, label: string) => void;
  currentStep: string;
  goToStep: (id: string) => void;
  nextStep: () => void;
  previousStep: () => void;
  isLastStep: boolean;
  isFirstStep: boolean;
  totalSteps: number;
}

const ModalContext = createContext<ModalContextType | null>(null);

export const useModalContext = () => {
  const context = useContext(ModalContext);
  if (!context) {
    throw new Error('useModalContext must be used within a Modal');
  }
  return context;
};

// ============================================================================
// TYPES
// ============================================================================

export type ModalSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | '4xl' | '5xl' | 'full' | 'screen';

export type ModalVariant = 'default' | 'success' | 'error' | 'warning' | 'info' | 'confirm' | 'danger';

export type ModalAnimation = 'fade' | 'slide-up' | 'slide-down' | 'slide-left' | 'slide-right' | 'scale' | 'bounce' | 'none';

export type ModalPlacement = 'center' | 'top' | 'bottom' | 'left' | 'right' | 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';

export interface ModalStep {
  id: string;
  label: string;
  description?: string;
  icon?: ReactNode;
}

// ============================================================================
// PROPS
// ============================================================================

export interface ModalProps {
  // --- Contrôle ---
  isOpen: boolean;
  onClose: () => void;
  onAfterOpen?: () => void;
  onAfterClose?: () => void;
  onBeforeClose?: () => boolean | void;
  onOpenChange?: (isOpen: boolean) => void;

  // --- Contenu ---
  title?: ReactNode;
  subtitle?: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  header?: ReactNode;

  // --- Apparence ---
  size?: ModalSize;
  variant?: ModalVariant;
  animation?: ModalAnimation;
  placement?: ModalPlacement;
  className?: string;
  contentClassName?: string;
  overlayClassName?: string;
  headerClassName?: string;
  bodyClassName?: string;
  footerClassName?: string;
  titleClassName?: string;
  subtitleClassName?: string;
  descriptionClassName?: string;
  iconClassName?: string;

  // --- Icône ---
  icon?: ReactNode;
  iconColor?: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'brand';
  iconPosition?: 'left' | 'top' | 'right' | 'center';

  // --- Comportement ---
  disableOutsideClick?: boolean;
  disableEscapeKey?: boolean;
  showCloseButton?: boolean;
  closeButtonPosition?: 'top-right' | 'top-left' | 'none';
  centered?: boolean;
  isLoading?: boolean;
  loadingText?: string;
  fullHeight?: boolean;
  lockScroll?: boolean;
  closeOnOverlayClick?: boolean;
  trapFocus?: boolean;
  restoreFocus?: boolean;
  autoFocus?: boolean;
  initialFocusRef?: React.RefObject<HTMLElement>;

  // --- Boutons ---
  confirmText?: string;
  cancelText?: string;
  onConfirm?: () => void | Promise<void>;
  onCancel?: () => void | Promise<void>;
  confirmButtonProps?: Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'onClick'>;
  cancelButtonProps?: Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'onClick'>;
  showConfirmButton?: boolean;
  showCancelButton?: boolean;
  confirmDisabled?: boolean;
  cancelDisabled?: boolean;
  confirmLoading?: boolean;
  confirmVariant?: 'primary' | 'success' | 'danger' | 'warning' | 'ghost' | 'outline';
  cancelVariant?: 'primary' | 'success' | 'danger' | 'warning' | 'ghost' | 'outline';

  // --- Étapes (Wizard) ---
  steps?: ModalStep[];
  currentStep?: string;
  onStepChange?: (stepId: string) => void;
  showStepIndicator?: boolean;
  showStepNavigation?: boolean;
  stepNavigationPosition?: 'top' | 'bottom' | 'both';

  // --- Accessibilité ---
  ariaLabel?: string;
  ariaDescribedby?: string;
  role?: 'dialog' | 'alertdialog';
  id?: string;

  // --- Avancé ---
  zIndex?: number;
  minHeight?: string | number;
  maxHeight?: string | number;
  minWidth?: string | number;
  maxWidth?: string | number;
  padding?: string | number;
  radius?: string | number;
  shadow?: 'none' | 'sm' | 'md' | 'lg' | 'xl' | '2xl';
  backdrop?: 'none' | 'blur' | 'dark' | 'blur-dark';
  backdropOpacity?: number;
  transitionDuration?: number;
  delay?: number;
  portalContainer?: HTMLElement | null;
  preventScroll?: boolean;
  disableAutoClose?: boolean;
  persistOnClose?: boolean;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
  onFocus?: () => void;
  onBlur?: () => void;
  onKeyDown?: (e: React.KeyboardEvent) => void;
}

// ============================================================================
// CONSTANTS
// ============================================================================

const SIZE_MAP: Record<ModalSize, string> = {
  xs: 'max-w-xs',
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
  '2xl': 'max-w-2xl',
  '3xl': 'max-w-3xl',
  '4xl': 'max-w-4xl',
  '5xl': 'max-w-5xl',
  full: 'max-w-full mx-4',
  screen: 'max-w-screen-2xl mx-4',
};

const VARIANT_ICON_MAP: Record<ModalVariant, ReactNode> = {
  default: null,
  success: <CheckCircleIcon className="h-6 w-6" />,
  error: <ExclamationCircleIcon className="h-6 w-6" />,
  warning: <ExclamationTriangleIcon className="h-6 w-6" />,
  info: <InformationCircleIcon className="h-6 w-6" />,
  confirm: <QuestionMarkCircleIcon className="h-6 w-6" />,
  danger: <ExclamationTriangleIcon className="h-6 w-6" />,
};

const VARIANT_COLOR_MAP: Record<ModalVariant, string> = {
  default: 'text-gray-600 dark:text-gray-400',
  success: 'text-green-500 dark:text-green-400',
  error: 'text-red-500 dark:text-red-400',
  warning: 'text-yellow-500 dark:text-yellow-400',
  info: 'text-blue-500 dark:text-blue-400',
  confirm: 'text-brand-500 dark:text-brand-400',
  danger: 'text-red-500 dark:text-red-400',
};

const ICON_COLOR_MAP: Record<NonNullable<ModalProps['iconColor']>, string> = {
  primary: 'text-brand-500 dark:text-brand-400',
  success: 'text-green-500 dark:text-green-400',
  warning: 'text-yellow-500 dark:text-yellow-400',
  danger: 'text-red-500 dark:text-red-400',
  info: 'text-blue-500 dark:text-blue-400',
  neutral: 'text-gray-400 dark:text-gray-500',
  brand: 'text-brand-500 dark:text-brand-400',
};

const SHADOW_MAP: Record<NonNullable<ModalProps['shadow']>, string> = {
  none: 'shadow-none',
  sm: 'shadow-sm',
  md: 'shadow-md',
  lg: 'shadow-lg',
  xl: 'shadow-xl',
  '2xl': 'shadow-2xl',
};

const BACKDROP_MAP: Record<NonNullable<ModalProps['backdrop']>, string> = {
  none: 'bg-transparent',
  dark: 'bg-black/70',
  blur: 'backdrop-blur-sm bg-black/30',
  'blur-dark': 'backdrop-blur-md bg-black/50',
};

const ANIMATION_MAP: Record<ModalAnimation, Record<'enter' | 'enterFrom' | 'enterTo' | 'leave' | 'leaveFrom' | 'leaveTo', string>> = {
  fade: {
    enter: 'transition-opacity duration-300 ease-out',
    enterFrom: 'opacity-0',
    enterTo: 'opacity-100',
    leave: 'transition-opacity duration-200 ease-in',
    leaveFrom: 'opacity-100',
    leaveTo: 'opacity-0',
  },
  'slide-up': {
    enter: 'transition-all duration-300 ease-out',
    enterFrom: 'opacity-0 translate-y-8',
    enterTo: 'opacity-100 translate-y-0',
    leave: 'transition-all duration-200 ease-in',
    leaveFrom: 'opacity-100 translate-y-0',
    leaveTo: 'opacity-0 translate-y-8',
  },
  'slide-down': {
    enter: 'transition-all duration-300 ease-out',
    enterFrom: 'opacity-0 -translate-y-8',
    enterTo: 'opacity-100 translate-y-0',
    leave: 'transition-all duration-200 ease-in',
    leaveFrom: 'opacity-100 translate-y-0',
    leaveTo: 'opacity-0 -translate-y-8',
  },
  'slide-left': {
    enter: 'transition-all duration-300 ease-out',
    enterFrom: 'opacity-0 translate-x-8',
    enterTo: 'opacity-100 translate-x-0',
    leave: 'transition-all duration-200 ease-in',
    leaveFrom: 'opacity-100 translate-x-0',
    leaveTo: 'opacity-0 translate-x-8',
  },
  'slide-right': {
    enter: 'transition-all duration-300 ease-out',
    enterFrom: 'opacity-0 -translate-x-8',
    enterTo: 'opacity-100 translate-x-0',
    leave: 'transition-all duration-200 ease-in',
    leaveFrom: 'opacity-100 translate-x-0',
    leaveTo: 'opacity-0 -translate-x-8',
  },
  scale: {
    enter: 'transition-all duration-300 ease-out',
    enterFrom: 'opacity-0 scale-95',
    enterTo: 'opacity-100 scale-100',
    leave: 'transition-all duration-200 ease-in',
    leaveFrom: 'opacity-100 scale-100',
    leaveTo: 'opacity-0 scale-95',
  },
  bounce: {
    enter: 'transition-all duration-500 ease-out',
    enterFrom: 'opacity-0 scale-50',
    enterTo: 'opacity-100 scale-100',
    leave: 'transition-all duration-300 ease-in',
    leaveFrom: 'opacity-100 scale-100',
    leaveTo: 'opacity-0 scale-50',
  },
  none: {
    enter: 'duration-0',
    enterFrom: '',
    enterTo: '',
    leave: 'duration-0',
    leaveFrom: '',
    leaveTo: '',
  },
};

const PLACEMENT_MAP: Record<ModalPlacement, string> = {
  center: 'items-center',
  top: 'items-start pt-16',
  bottom: 'items-end pb-16',
  left: 'items-center justify-start pl-16',
  right: 'items-center justify-end pr-16',
  'top-left': 'items-start justify-start pt-16 pl-16',
  'top-right': 'items-start justify-end pt-16 pr-16',
  'bottom-left': 'items-end justify-start pb-16 pl-16',
  'bottom-right': 'items-end justify-end pb-16 pr-16',
};

// ============================================================================
// COMPOSANTS INTERNES
// ============================================================================

// --- Bouton de confirmation générique ---
interface ModalButtonProps {
  children: ReactNode;
  variant?: 'primary' | 'success' | 'danger' | 'warning' | 'ghost' | 'outline';
  disabled?: boolean;
  loading?: boolean;
  onClick?: () => void | Promise<void>;
  className?: string;
}

const ModalButton: React.FC<ModalButtonProps> = ({
  children,
  variant = 'primary',
  disabled = false,
  loading = false,
  onClick,
  className,
}) => {
  const baseStyles = 'inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed min-w-[80px]';

  const variantStyles = {
    primary: 'bg-brand-500 text-white hover:bg-brand-600 focus:ring-brand-500 dark:bg-brand-600 dark:hover:bg-brand-700',
    success: 'bg-green-500 text-white hover:bg-green-600 focus:ring-green-500 dark:bg-green-600 dark:hover:bg-green-700',
    danger: 'bg-red-500 text-white hover:bg-red-600 focus:ring-red-500 dark:bg-red-600 dark:hover:bg-red-700',
    warning: 'bg-yellow-500 text-white hover:bg-yellow-600 focus:ring-yellow-500 dark:bg-yellow-600 dark:hover:bg-yellow-700',
    ghost: 'bg-transparent text-gray-600 hover:bg-gray-100 focus:ring-gray-400 dark:text-gray-400 dark:hover:bg-gray-800',
    outline: 'bg-transparent border-2 border-gray-300 text-gray-700 hover:bg-gray-50 focus:ring-gray-400 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800',
  };

  return (
    <button
      className={cn(baseStyles, variantStyles[variant], className)}
      disabled={disabled || loading}
      onClick={onClick}
    >
      {loading && <ArrowPathIcon className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
};

// --- Indicateur d'étapes ---
interface StepIndicatorProps {
  steps: ModalStep[];
  currentStep: string;
  onStepClick?: (stepId: string) => void;
  className?: string;
}

const StepIndicator: React.FC<StepIndicatorProps> = ({
  steps,
  currentStep,
  onStepClick,
  className,
}) => {
  const currentIndex = steps.findIndex((s) => s.id === currentStep);

  return (
    <div className={cn('flex items-center gap-2 px-6 py-4', className)}>
      {steps.map((step, index) => {
        const isActive = step.id === currentStep;
        const isCompleted = index < currentIndex;
        const isClickable = onStepClick && (isActive || isCompleted);

        return (
          <Fragment key={step.id}>
            <button
              className={cn(
                'flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium transition-all',
                isActive && 'bg-brand-100 text-brand-700 dark:bg-brand-900/30 dark:text-brand-400',
                isCompleted && 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
                !isActive && !isCompleted && 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
                isClickable && 'hover:opacity-80 cursor-pointer',
                !isClickable && 'cursor-default'
              )}
              onClick={() => {
                if (isClickable && onStepClick) {
                  onStepClick(step.id);
                }
              }}
              disabled={!isClickable}
            >
              {step.icon || (
                <span className="flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold">
                  {isCompleted ? '✓' : index + 1}
                </span>
              )}
              <span className="hidden sm:inline">{step.label}</span>
            </button>
            {index < steps.length - 1 && (
              <div className="h-0.5 flex-1 bg-gray-200 dark:bg-gray-700" />
            )}
          </Fragment>
        );
      })}
    </div>
  );
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const Modal = forwardRef<HTMLDivElement, ModalProps>(
  (props, ref) => {
    const {
      // Contrôle
      isOpen,
      onClose,
      onAfterOpen,
      onAfterClose,
      onBeforeClose,
      onOpenChange,

      // Contenu
      title,
      subtitle,
      description,
      children,
      footer,
      header,

      // Apparence
      size = 'md',
      variant = 'default',
      animation = 'scale',
      placement = 'center',
      className,
      contentClassName,
      overlayClassName,
      headerClassName,
      bodyClassName,
      footerClassName,
      titleClassName,
      subtitleClassName,
      descriptionClassName,
      iconClassName,

      // Icône
      icon,
      iconColor = 'neutral',
      iconPosition = 'left',

      // Comportement
      disableOutsideClick = false,
      disableEscapeKey = false,
      showCloseButton = true,
      closeButtonPosition = 'top-right',
      centered = true,
      isLoading: externalLoading = false,
      loadingText = 'Chargement...',
      fullHeight = false,
      lockScroll = true,
      closeOnOverlayClick = true,
      trapFocus = true,
      restoreFocus = true,
      autoFocus = true,
      initialFocusRef,

      // Boutons
      confirmText = 'Confirmer',
      cancelText = 'Annuler',
      onConfirm,
      onCancel,
      confirmButtonProps = {},
      cancelButtonProps = {},
      showConfirmButton = false,
      showCancelButton = false,
      confirmDisabled = false,
      cancelDisabled = false,
      confirmLoading = false,
      confirmVariant = 'primary',
      cancelVariant = 'ghost',

      // Étapes
      steps = [],
      currentStep: externalStep,
      onStepChange,
      showStepIndicator = false,
      showStepNavigation = false,
      stepNavigationPosition = 'both',

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      role = 'dialog',
      id,

      // Avancé
      zIndex = 1000,
      minHeight,
      maxHeight,
      minWidth,
      maxWidth,
      padding,
      radius = 'rounded-2xl',
      shadow = '2xl',
      backdrop = 'blur-dark',
      backdropOpacity = 0.7,
      transitionDuration = 300,
      delay = 0,
      portalContainer = null,
      preventScroll = false,
      disableAutoClose = false,
      persistOnClose = false,
      onMouseEnter,
      onMouseLeave,
      onFocus,
      onBlur,
      onKeyDown,
    } = props;

    // ========================================================================
    // ÉTATS INTERNES
    // ========================================================================

    const [internalStep, setInternalStep] = useState<string>(
      steps.length > 0 ? steps[0]?.id || '' : ''
    );
    const [internalLoading, setInternalLoading] = useState(false);
    const [internalError, setInternalError] = useState<string | null>(null);
    const [isVisible, setIsVisible] = useState(false);
    const [isMounted, setIsMounted] = useState(false);

    const closeButtonRef = useRef<HTMLButtonElement>(null);
    const initialFocus = useRef<HTMLElement | null>(null);
    const modalRef = useRef<HTMLDivElement>(null);
    const uniqueId = useId();
    const modalId = id || `nexus-modal-${uniqueId}`;

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const currentStep = externalStep || internalStep;
    const currentStepIndex = steps.findIndex((s) => s.id === currentStep);
    const totalSteps = steps.length;
    const isFirstStep = currentStepIndex === 0;
    const isLastStep = currentStepIndex === totalSteps - 1;
    const isLoading = externalLoading || internalLoading;
    const showClose = showCloseButton && closeButtonPosition !== 'none';

    const hasIcon = icon || (variant !== 'default' && VARIANT_ICON_MAP[variant]);

    const finalIcon = icon || (variant !== 'default' ? VARIANT_ICON_MAP[variant] : null);
    const finalIconColor = iconColor || (variant !== 'default' ? VARIANT_COLOR_MAP[variant] : 'neutral');

    // ========================================================================
    // CONTEXT
    // ========================================================================

    const contextValue = useMemo<ModalContextType>(
      () => ({
        isOpen,
        onClose,
        size,
        isLoading,
        setIsLoading: setInternalLoading,
        setError: setInternalError,
        registerStep: () => {},
        currentStep,
        goToStep: (id: string) => {
          if (onStepChange) onStepChange(id);
          setInternalStep(id);
        },
        nextStep: () => {
          if (!isLastStep && steps[currentStepIndex + 1]) {
            const nextId = steps[currentStepIndex + 1].id;
            if (onStepChange) onStepChange(nextId);
            setInternalStep(nextId);
          }
        },
        previousStep: () => {
          if (!isFirstStep && steps[currentStepIndex - 1]) {
            const prevId = steps[currentStepIndex - 1].id;
            if (onStepChange) onStepChange(prevId);
            setInternalStep(prevId);
          }
        },
        isLastStep,
        isFirstStep,
        totalSteps,
      }),
      [
        isOpen,
        onClose,
        size,
        isLoading,
        currentStep,
        steps,
        currentStepIndex,
        isLastStep,
        isFirstStep,
        totalSteps,
        onStepChange,
      ]
    );

    // ========================================================================
    // FERMETURE
    // ========================================================================

    const handleClose = useCallback(async (): Promise<void> => {
      if (isLoading || disableAutoClose) return;

      if (onBeforeClose) {
        const shouldClose = await onBeforeClose();
        if (shouldClose === false) return;
      }

      if (onOpenChange) onOpenChange(false);
      onClose();

      if (onAfterClose) {
        setTimeout(onAfterClose, transitionDuration);
      }
    }, [isLoading, disableAutoClose, onBeforeClose, onOpenChange, onClose, onAfterClose, transitionDuration]);

    // ========================================================================
    // CONFIRMATION
    // ========================================================================

    const handleConfirm = useCallback(async (): Promise<void> => {
      if (!onConfirm) return;

      setInternalLoading(true);
      try {
        await onConfirm();
        if (!persistOnClose) {
          await handleClose();
        }
      } catch (error) {
        setInternalError(error instanceof Error ? error.message : 'Une erreur est survenue');
      } finally {
        setInternalLoading(false);
      }
    }, [onConfirm, persistOnClose, handleClose]);

    // ========================================================================
    // ANNULATION
    // ========================================================================

    const handleCancel = useCallback(async (): Promise<void> => {
      if (onCancel) {
        setInternalLoading(true);
        try {
          await onCancel();
        } catch (error) {
          setInternalError(error instanceof Error ? error.message : 'Une erreur est survenue');
        } finally {
          setInternalLoading(false);
        }
      }
      await handleClose();
    }, [onCancel, handleClose]);

    // ========================================================================
    // NAVIGATION DES ÉTAPES
    // ========================================================================

    const handleStepChange = useCallback(
      (stepId: string) => {
        if (onStepChange) onStepChange(stepId);
        setInternalStep(stepId);
      },
      [onStepChange]
    );

    // ========================================================================
    // EFFETS
    // ========================================================================

    // Montage / Démonte
    useEffect(() => {
      if (isOpen) {
        setIsMounted(true);
        setTimeout(() => setIsVisible(true), delay);
        if (onAfterOpen) setTimeout(onAfterOpen, transitionDuration + delay);
      } else {
        setIsVisible(false);
        setTimeout(() => setIsMounted(false), transitionDuration);
      }
    }, [isOpen, delay, transitionDuration, onAfterOpen]);

    // Focus automatique
    useEffect(() => {
      if (isOpen && autoFocus) {
        const target = initialFocusRef?.current || closeButtonRef.current;
        if (target) {
          setTimeout(() => target.focus(), 100);
        }
      }
    }, [isOpen, autoFocus, initialFocusRef]);

    // Verrouillage du scroll
    useEffect(() => {
      if (!lockScroll || preventScroll) return;

      const body = document.body;
      if (isOpen) {
        const scrollY = window.scrollY;
        body.style.overflow = 'hidden';
        body.style.position = 'fixed';
        body.style.top = `-${scrollY}px`;
        body.style.width = '100%';
      } else {
        const scrollY = parseInt(body.style.top || '0', 10) * -1;
        body.style.overflow = '';
        body.style.position = '';
        body.style.top = '';
        body.style.width = '';
        window.scrollTo(0, scrollY);
      }

      return () => {
        body.style.overflow = '';
        body.style.position = '';
        body.style.top = '';
        body.style.width = '';
      };
    }, [isOpen, lockScroll, preventScroll]);

    // Raccourcis clavier
    useEffect(() => {
      if (disableEscapeKey) return;

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape' && isOpen && !disableOutsideClick) {
          e.preventDefault();
          handleClose();
        }
      };

      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen, disableEscapeKey, disableOutsideClick, handleClose]);

    // Synchronisation externe
    useEffect(() => {
      if (onOpenChange) onOpenChange(isOpen);
    }, [isOpen, onOpenChange]);

    // Reset des erreurs à l'ouverture
    useEffect(() => {
      if (isOpen) {
        setInternalError(null);
      }
    }, [isOpen]);

    // ========================================================================
    // RENDU
    // ========================================================================

    if (!isMounted) return null;

    const animationStyles = ANIMATION_MAP[animation];
    const placementStyles = centered ? 'items-center' : PLACEMENT_MAP[placement];

    const renderHeader = (): ReactNode => {
      if (header) return header;

      if (!title && !hasIcon && !showClose) return null;

      const iconEl = hasIcon && (
        <span className={cn('flex-shrink-0', ICON_COLOR_MAP[finalIconColor], iconClassName)}>
          {finalIcon}
        </span>
      );

      const isIconLeft = iconPosition === 'left' || iconPosition === 'center';
      const isIconRight = iconPosition === 'right';
      const isIconTop = iconPosition === 'top';

      return (
        <div
          className={cn(
            'flex items-start gap-3 px-6 py-4 border-b border-gray-200 dark:border-gray-700',
            isIconTop && 'flex-col items-center text-center',
            headerClassName
          )}
        >
          {showClose && closeButtonPosition === 'top-left' && (
            <button
              ref={closeButtonRef}
              type="button"
              className="flex-shrink-0 rounded-lg p-1.5 text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-brand-500 transition-colors"
              onClick={handleClose}
              disabled={isLoading}
              aria-label="Fermer la modale"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          )}

          <div className={cn('flex-1 min-w-0', isIconTop && 'flex flex-col items-center')}>
            {isIconTop && iconEl}
            <div className={cn('flex items-center gap-3', !isIconTop && 'w-full')}>
              {isIconLeft && iconEl && !isIconTop && (
                <div className="flex-shrink-0">{iconEl}</div>
              )}
              <div className="flex-1 min-w-0">
                {title && (
                  <Dialog.Title
                    as={typeof title === 'string' ? 'h3' : 'div'}
                    className={cn(
                      'text-lg font-semibold leading-6 text-gray-900 dark:text-white',
                      isIconTop && 'text-center',
                      titleClassName
                    )}
                  >
                    {title}
                  </Dialog.Title>
                )}
                {subtitle && (
                  <Dialog.Description
                    as={typeof subtitle === 'string' ? 'p' : 'div'}
                    className={cn(
                      'mt-1 text-sm text-gray-500 dark:text-gray-400',
                      isIconTop && 'text-center',
                      subtitleClassName
                    )}
                  >
                    {subtitle}
                  </Dialog.Description>
                )}
                {description && (
                  <div
                    className={cn(
                      'mt-2 text-sm text-gray-600 dark:text-gray-300',
                      isIconTop && 'text-center',
                      descriptionClassName
                    )}
                  >
                    {description}
                  </div>
                )}
              </div>
              {isIconRight && iconEl && !isIconTop && (
                <div className="flex-shrink-0">{iconEl}</div>
              )}
            </div>
          </div>

          {showClose && closeButtonPosition === 'top-right' && (
            <button
              ref={closeButtonRef}
              type="button"
              className="flex-shrink-0 rounded-lg p-1.5 text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-brand-500 transition-colors"
              onClick={handleClose}
              disabled={isLoading}
              aria-label="Fermer la modale"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          )}
        </div>
      );
    };

    const renderSteps = (position: 'top' | 'bottom'): ReactNode => {
      if (!showStepIndicator || steps.length === 0) return null;
      if (stepNavigationPosition === 'both' || stepNavigationPosition === position) {
        return (
          <StepIndicator
            steps={steps}
            currentStep={currentStep}
            onStepClick={onStepChange && handleStepChange}
            className={position === 'bottom' ? 'border-t border-gray-200 dark:border-gray-700' : ''}
          />
        );
      }
      return null;
    };

    const renderBody = (): ReactNode => {
      if (isLoading && loadingText) {
        return (
          <div className="flex flex-col items-center justify-center gap-3 py-8">
            <ArrowPathIcon className="h-8 w-8 animate-spin text-brand-500" />
            <p className="text-sm text-gray-500 dark:text-gray-400">{loadingText}</p>
          </div>
        );
      }

      if (internalError) {
        return (
          <div className="rounded-lg bg-red-50 dark:bg-red-900/20 p-4 border border-red-200 dark:border-red-800">
            <div className="flex items-start gap-3">
              <ExclamationCircleIcon className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-800 dark:text-red-200">
                  Erreur
                </p>
                <p className="text-sm text-red-700 dark:text-red-300">
                  {internalError}
                </p>
              </div>
            </div>
          </div>
        );
      }

      // Rendu du contenu avec contexte pour les étapes
      if (steps.length > 0) {
        return (
          <ModalContext.Provider value={contextValue}>
            <div className="space-y-4">
              {Children.map(children, (child) => {
                if (isValidElement(child) && (child.type as any).displayName === 'ModalStep') {
                  return cloneElement(child, {
                    stepId: child.props.stepId || child.props.id,
                    ...child.props,
                  });
                }
                return child;
              })}
              {renderStepContent()}
            </div>
          </ModalContext.Provider>
        );
      }

      return children;
    };

    const renderStepContent = (): ReactNode => {
      if (steps.length === 0) return null;

      const currentStepData = steps.find((s) => s.id === currentStep);
      if (!currentStepData) return null;

      return (
        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
            className="space-y-4"
          >
            {currentStepData.description && (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {currentStepData.description}
              </p>
            )}
            {Children.map(children, (child) => {
              if (isValidElement(child) && (child.type as any).displayName === 'ModalStep') {
                if (child.props.stepId === currentStep || child.props.id === currentStep) {
                  return child;
                }
                return null;
              }
              return null;
            })}
          </motion.div>
        </AnimatePresence>
      );
    };

    const renderFooter = (): ReactNode => {
      if (footer) return footer;

      const hasConfirm = showConfirmButton || onConfirm;
      const hasCancel = showCancelButton || onCancel;

      if (!hasConfirm && !hasCancel && steps.length === 0) return null;

      return (
        <div
          className={cn(
            'flex flex-wrap items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700',
            footerClassName
          )}
        >
          {/* Navigation des étapes */}
          {steps.length > 0 && showStepNavigation && (
            <div className="flex items-center gap-2 mr-auto">
              <button
                type="button"
                className="rounded-lg p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                onClick={contextValue.previousStep}
                disabled={isFirstStep || isLoading}
                aria-label="Étape précédente"
              >
                <ChevronLeftIcon className="h-5 w-5" />
              </button>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {currentStepIndex + 1} / {totalSteps}
              </span>
              <button
                type="button"
                className="rounded-lg p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                onClick={contextValue.nextStep}
                disabled={isLastStep || isLoading}
                aria-label="Étape suivante"
              >
                <ChevronRightIcon className="h-5 w-5" />
              </button>
            </div>
          )}

          {/* Boutons d'action */}
          {hasCancel && (
            <ModalButton
              variant={cancelVariant}
              disabled={cancelDisabled || isLoading}
              loading={isLoading}
              onClick={handleCancel}
              className={cancelButtonProps.className}
              {...cancelButtonProps}
            >
              {cancelText}
            </ModalButton>
          )}

          {hasConfirm && (
            <ModalButton
              variant={confirmVariant}
              disabled={confirmDisabled || isLoading}
              loading={confirmLoading || isLoading}
              onClick={handleConfirm}
              className={confirmButtonProps.className}
              {...confirmButtonProps}
            >
              {confirmText}
            </ModalButton>
          )}
        </div>
      );
    };

    const overlayStyles = {
      backgroundColor: backdrop.includes('blur')
        ? undefined
        : `rgba(0, 0, 0, ${backdropOpacity})`,
    };

    return (
      <Transition appear show={isOpen} as={Fragment}>
        <Dialog
          as="div"
          className={cn('relative', `z-${zIndex}`)}
          onClose={disableOutsideClick || !closeOnOverlayClick ? () => {} : handleClose}
          initialFocus={initialFocusRef || closeButtonRef}
          static={false}
          open={isOpen}
          onCloseComplete={onAfterClose}
          aria-label={ariaLabel}
          aria-describedby={ariaDescribedby}
          role={role}
          id={modalId}
        >
          {/* Overlay */}
          <TransitionChild
            as={Fragment}
            enter={animationStyles.enter}
            enterFrom={animationStyles.enterFrom}
            enterTo={animationStyles.enterTo}
            leave={animationStyles.leave}
            leaveFrom={animationStyles.leaveFrom}
            leaveTo={animationStyles.leaveTo}
          >
            <div
              className={cn(
                'fixed inset-0',
                BACKDROP_MAP[backdrop],
                overlayClassName
              )}
              style={overlayStyles}
              onClick={(e) => {
                if (closeOnOverlayClick && !disableOutsideClick) {
                  e.stopPropagation();
                  handleClose();
                }
              }}
            />
          </TransitionChild>

          {/* Conteneur principal */}
          <div
            className={cn(
              'fixed inset-0 overflow-y-auto',
              preventScroll && 'overflow-hidden'
            )}
            onMouseEnter={onMouseEnter}
            onMouseLeave={onMouseLeave}
            onFocus={onFocus}
            onBlur={onBlur}
            onKeyDown={onKeyDown}
          >
            <div
              className={cn(
                'flex min-h-full p-4 text-center',
                placementStyles,
                className
              )}
            >
              <TransitionChild
                as={Fragment}
                enter={animationStyles.enter}
                enterFrom={animationStyles.enterFrom}
                enterTo={animationStyles.enterTo}
                leave={animationStyles.leave}
                leaveFrom={animationStyles.leaveFrom}
                leaveTo={animationStyles.leaveTo}
              >
                <Dialog.Panel
                  ref={(node) => {
                    if (typeof ref === 'function') ref(node);
                    else if (ref) ref.current = node;
                    modalRef.current = node;
                  }}
                  className={cn(
                    'relative w-full transform bg-white dark:bg-gray-900 text-left align-middle transition-all',
                    radius,
                    SHADOW_MAP[shadow],
                    SIZE_MAP[size],
                    fullHeight ? 'h-[90vh] flex flex-col' : '',
                    contentClassName
                  )}
                  style={{
                    minHeight: minHeight,
                    maxHeight: maxHeight,
                    minWidth: minWidth,
                    maxWidth: maxWidth,
                    padding: padding,
                  }}
                >
                  {/* Header */}
                  {renderHeader()}

                  {/* Indicateur d'étapes - Haut */}
                  {renderSteps('top')}

                  {/* Corps */}
                  <div
                    className={cn(
                      'flex-1',
                      fullHeight ? 'flex-1 overflow-y-auto' : '',
                      bodyClassName
                    )}
                  >
                    {renderBody()}
                  </div>

                  {/* Indicateur d'étapes - Bas */}
                  {renderSteps('bottom')}

                  {/* Footer */}
                  {renderFooter()}
                </Dialog.Panel>
              </TransitionChild>
            </div>
          </div>
        </Dialog>
      </Transition>
    );
  }
);

Modal.displayName = 'Modal';

// ============================================================================
// SOUS-COMPOSANT : Modal.Step
// ============================================================================

interface ModalStepProps {
  stepId?: string;
  id?: string;
  children: ReactNode;
}

export const ModalStep: React.FC<ModalStepProps> & { displayName: string } = ({ stepId, id, children }) => {
  const context = useModalContext();
  const currentStep = context?.currentStep || '';
  const isActive = (stepId || id) === currentStep;

  if (!isActive) return null;

  return <>{children}</>;
};

ModalStep.displayName = 'ModalStep';

// ============================================================================
// HOOKS
// ============================================================================

/**
 * Hook pour gérer l'état d'une modale
 */
export const useModal = (initialState = false) => {
  const [isOpen, setIsOpen] = React.useState(initialState);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((prev) => !prev), []);

  return {
    isOpen,
    open,
    close,
    toggle,
    setOpen: setIsOpen,
  };
};

/**
 * Hook pour gérer une modale avec des étapes
 */
export const useModalWizard = (initialStep = 0, steps: string[] = []) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const [currentStepIndex, setCurrentStepIndex] = React.useState(initialStep);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((prev) => !prev), []);

  const goToStep = useCallback(
    (index: number) => {
      if (index >= 0 && index < steps.length) {
        setCurrentStepIndex(index);
      }
    },
    [steps.length]
  );

  const nextStep = useCallback(() => {
    if (currentStepIndex < steps.length - 1) {
      setCurrentStepIndex((prev) => prev + 1);
    }
  }, [currentStepIndex, steps.length]);

  const previousStep = useCallback(() => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex((prev) => prev - 1);
    }
  }, [currentStepIndex]);

  const reset = useCallback(() => {
    setCurrentStepIndex(0);
  }, []);

  const isFirstStep = currentStepIndex === 0;
  const isLastStep = currentStepIndex === steps.length - 1;

  return {
    isOpen,
    open,
    close,
    toggle,
    setOpen: setIsOpen,
    currentStepIndex,
    currentStepId: steps[currentStepIndex] || '',
    goToStep,
    nextStep,
    previousStep,
    reset,
    isFirstStep,
    isLastStep,
    totalSteps: steps.length,
  };
};

/**
 * Hook pour les confirmations avec modale
 */
export const useConfirm = () => {
  const [isOpen, setIsOpen] = React.useState(false);
  const [resolve, setResolve] = React.useState<((value: boolean) => void) | null>(null);

  const confirm = useCallback((): Promise<boolean> => {
    return new Promise((res) => {
      setIsOpen(true);
      setResolve(() => res);
    });
  }, []);

  const handleConfirm = useCallback(() => {
    setIsOpen(false);
    if (resolve) resolve(true);
  }, [resolve]);

  const handleCancel = useCallback(() => {
    setIsOpen(false);
    if (resolve) resolve(false);
  }, [resolve]);

  return {
    isOpen,
    confirm,
    handleConfirm,
    handleCancel,
    onClose: handleCancel,
  };
};

// ============================================================================
// EXPORTS PAR DÉFAUT
// ============================================================================

export default Object.assign(Modal, {
  Step: ModalStep,
});

// apps/web/src/components/common/Progress.tsx
'use client';

import React, {
  ReactNode,
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  forwardRef,
  Ref,
  createContext,
  useContext,
  useId,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence, useMotionValue, useSpring, useTransform } from 'framer-motion';
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  InformationCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  ClockIcon,
  PlayIcon,
  PauseIcon,
  StopIcon,
  RefreshIcon,
  DownloadIcon,
  UploadIcon,
  CloudUploadIcon,
  CloudDownloadIcon,
  DocumentTextIcon,
  FolderIcon,
  FolderOpenIcon,
  TrashIcon,
  PlusIcon,
  MinusIcon,
  CheckIcon,
  ExclamationTriangleIcon,
  QuestionMarkCircleIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
  InformationCircleIcon as InformationCircleSolid,
  XCircleIcon as XCircleSolid,
  ClockIcon as ClockSolid,
} from '@heroicons/react/24/solid';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';
import { Separator } from '@/components/common/Separator';

// ============================================================================
// TYPES
// ============================================================================

export type ProgressVariant = 'default' | 'success' | 'error' | 'warning' | 'info' | 'gradient' | 'rainbow' | 'striped' | 'animated';

export type ProgressSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

export type ProgressShape = 'default' | 'rounded' | 'pill' | 'square';

export type ProgressStatus = 'idle' | 'active' | 'paused' | 'complete' | 'error' | 'warning';

export type ProgressDirection = 'horizontal' | 'vertical';

export type ProgressLabelPosition = 'top' | 'bottom' | 'left' | 'right' | 'inside' | 'none';

export type ProgressAnimation = 'ease' | 'linear' | 'ease-in' | 'ease-out' | 'ease-in-out';

export interface ProgressStep {
  id: string;
  label: string;
  description?: string;
  status?: ProgressStatus;
  icon?: ReactNode;
  isOptional?: boolean;
}

export interface ProgressProps {
  // --- Contrôle ---
  /** Valeur de progression (0-100) */
  value?: number;
  /** Valeur par défaut */
  defaultValue?: number;
  /** Callback lors du changement de valeur */
  onValueChange?: (value: number) => void;
  /** Callback à la fin de la progression */
  onComplete?: () => void;

  // --- Apparence ---
  /** Variante de la barre */
  variant?: ProgressVariant;
  /** Taille de la barre */
  size?: ProgressSize;
  /** Forme de la barre */
  shape?: ProgressShape;
  /** Direction de la barre */
  direction?: ProgressDirection;
  /** Position du libellé */
  labelPosition?: ProgressLabelPosition;
  /** Animation de la barre */
  animation?: ProgressAnimation;
  /** Classe CSS additionnelle */
  className?: string;
  /** Classe CSS pour la barre */
  barClassName?: string;
  /** Classe CSS pour le conteneur */
  containerClassName?: string;
  /** Classe CSS pour le libellé */
  labelClassName?: string;
  /** Classe CSS pour la valeur */
  valueClassName?: string;

  // --- Contenu ---
  /** Libellé de progression */
  label?: ReactNode;
  /** Formatage de la valeur */
  formatValue?: (value: number) => string;
  /** Icône de progression */
  icon?: ReactNode;
  /** Icône de succès */
  successIcon?: ReactNode;
  /** Icône d'erreur */
  errorIcon?: ReactNode;
  /** Afficher la valeur en pourcentage */
  showValue?: boolean;
  /** Afficher le statut */
  showStatus?: boolean;
  /** Afficher l'icône de statut */
  showStatusIcon?: boolean;
  /** Afficher les étapes */
  showSteps?: boolean;
  /** Afficher le temps restant */
  showTimeRemaining?: boolean;

  // --- États ---
  /** Statut de progression */
  status?: ProgressStatus;
  /** État de chargement */
  isLoading?: boolean;
  /** État d'indéterminé */
  indeterminate?: boolean;
  /** État désactivé */
  disabled?: boolean;

  // --- Valeurs ---
  /** Valeur minimale */
  min?: number;
  /** Valeur maximale */
  max?: number;
  /** Seuil de succès */
  successThreshold?: number;
  /** Seuil d'avertissement */
  warningThreshold?: number;
  /** Seuil d'erreur */
  errorThreshold?: number;

  // --- Étapes ---
  /** Liste des étapes */
  steps?: ProgressStep[];
  /** Étape courante */
  currentStep?: string;
  /** Callback lors du changement d'étape */
  onStepChange?: (stepId: string) => void;

  // --- Contrôle ---
  /** Vitesse d'animation (ms) */
  animationDuration?: number;
  /** Délai de début (ms) */
  delay?: number;
  /** Intervalle d'auto-progression (ms) */
  autoIncrementInterval?: number;
  /** Incrément automatique */
  autoIncrement?: boolean;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ARIA describedby */
  ariaDescribedby?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Couleur personnalisée */
  color?: string;
  /** Couleur de fond personnalisée */
  backgroundColor?: string;
  /** Hauteur personnalisée */
  height?: string | number;
  /** Largeur personnalisée */
  width?: string | number;
  /** Rayon de bordure personnalisé */
  radius?: string | number;
  /** Motif de rayure */
  striped?: boolean;
  /** Animation de rayure */
  stripedAnimated?: boolean;
  /** Ombre */
  shadow?: boolean;
  /** Glow (lueur) */
  glow?: boolean;
  /** Dégradé */
  gradient?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const STATUS_ICON_MAP: Record<ProgressStatus, ReactNode> = {
  idle: <ClockIcon className="h-4 w-4" />,
  active: <ArrowPathIcon className="h-4 w-4 animate-spin" />,
  paused: <PauseIcon className="h-4 w-4" />,
  complete: <CheckCircleIcon className="h-4 w-4" />,
  error: <XCircleIcon className="h-4 w-4" />,
  warning: <ExclamationTriangleIcon className="h-4 w-4" />,
};

const STATUS_COLOR_MAP: Record<ProgressStatus, string> = {
  idle: 'text-gray-400',
  active: 'text-brand-500',
  paused: 'text-yellow-500',
  complete: 'text-green-500',
  error: 'text-red-500',
  warning: 'text-yellow-500',
};

const VARIANT_COLOR_MAP: Record<ProgressVariant, { bg: string; bar: string; text: string }> = {
  default: {
    bg: 'bg-gray-200 dark:bg-gray-700',
    bar: 'bg-brand-500 dark:bg-brand-400',
    text: 'text-brand-600 dark:text-brand-400',
  },
  success: {
    bg: 'bg-green-200 dark:bg-green-700',
    bar: 'bg-green-500 dark:bg-green-400',
    text: 'text-green-600 dark:text-green-400',
  },
  error: {
    bg: 'bg-red-200 dark:bg-red-700',
    bar: 'bg-red-500 dark:bg-red-400',
    text: 'text-red-600 dark:text-red-400',
  },
  warning: {
    bg: 'bg-yellow-200 dark:bg-yellow-700',
    bar: 'bg-yellow-500 dark:bg-yellow-400',
    text: 'text-yellow-600 dark:text-yellow-400',
  },
  info: {
    bg: 'bg-blue-200 dark:bg-blue-700',
    bar: 'bg-blue-500 dark:bg-blue-400',
    text: 'text-blue-600 dark:text-blue-400',
  },
  gradient: {
    bg: 'bg-gray-200 dark:bg-gray-700',
    bar: 'bg-gradient-to-r from-brand-400 via-brand-500 to-brand-600',
    text: 'text-brand-600 dark:text-brand-400',
  },
  rainbow: {
    bg: 'bg-gray-200 dark:bg-gray-700',
    bar: 'bg-gradient-to-r from-red-500 via-yellow-500 via-green-500 via-blue-500 to-purple-500',
    text: 'text-brand-600 dark:text-brand-400',
  },
  striped: {
    bg: 'bg-gray-200 dark:bg-gray-700',
    bar: 'bg-brand-500 dark:bg-brand-400',
    text: 'text-brand-600 dark:text-brand-400',
  },
  animated: {
    bg: 'bg-gray-200 dark:bg-gray-700',
    bar: 'bg-brand-500 dark:bg-brand-400',
    text: 'text-brand-600 dark:text-brand-400',
  },
};

const SIZE_MAP: Record<ProgressSize, { height: string; fontSize: string; gap: string }> = {
  xs: { height: 'h-1.5', fontSize: 'text-[10px]', gap: 'gap-1' },
  sm: { height: 'h-2', fontSize: 'text-xs', gap: 'gap-1.5' },
  md: { height: 'h-3', fontSize: 'text-sm', gap: 'gap-2' },
  lg: { height: 'h-4', fontSize: 'text-base', gap: 'gap-2.5' },
  xl: { height: 'h-5', fontSize: 'text-lg', gap: 'gap-3' },
};

const SHAPE_MAP: Record<ProgressShape, string> = {
  default: 'rounded-none',
  rounded: 'rounded-md',
  pill: 'rounded-full',
  square: 'rounded-sm',
};

const ANIMATION_TIMING_MAP: Record<ProgressAnimation, string> = {
  'ease': 'cubic-bezier(0.25, 0.1, 0.25, 1)',
  'linear': 'linear',
  'ease-in': 'cubic-bezier(0.42, 0, 1, 1)',
  'ease-out': 'cubic-bezier(0, 0, 0.58, 1)',
  'ease-in-out': 'cubic-bezier(0.42, 0, 0.58, 1)',
};

// ============================================================================
// CONTEXT
// ============================================================================

interface ProgressContextType {
  value: number;
  status: ProgressStatus;
  size: ProgressSize;
  variant: ProgressVariant;
  disabled: boolean;
  isLoading: boolean;
  setValue: (value: number) => void;
}

const ProgressContext = createContext<ProgressContextType | null>(null);

export const useProgressContext = () => {
  const context = useContext(ProgressContext);
  if (!context) {
    throw new Error('useProgressContext must be used within a Progress');
  }
  return context;
};

// ============================================================================
// COMPOSANTS INTERNES
// ============================================================================

// --- Barre de progression ---
interface ProgressBarProps {
  value: number;
  min: number;
  max: number;
  variant: ProgressVariant;
  size: ProgressSize;
  shape: ProgressShape;
  direction: ProgressDirection;
  animation: ProgressAnimation;
  animationDuration: number;
  indeterminate: boolean;
  disabled: boolean;
  className?: string;
  barClassName?: string;
  color?: string;
  backgroundColor?: string;
  height?: string | number;
  width?: string | number;
  radius?: string | number;
  striped: boolean;
  stripedAnimated: boolean;
  shadow: boolean;
  glow: boolean;
  gradient: boolean;
}

const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  min,
  max,
  variant,
  size,
  shape,
  direction,
  animation,
  animationDuration,
  indeterminate,
  disabled,
  className,
  barClassName,
  color,
  backgroundColor,
  height,
  width,
  radius,
  striped,
  stripedAnimated,
  shadow,
  glow,
  gradient,
}) => {
  const percentage = useMemo(() => {
    return Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
  }, [value, min, max]);

  const isHorizontal = direction === 'horizontal';
  const variantColors = VARIANT_COLOR_MAP[variant] || VARIANT_COLOR_MAP.default;
  const sizeClasses = SIZE_MAP[size] || SIZE_MAP.md;
  const shapeClasses = SHAPE_MAP[shape] || SHAPE_MAP.default;

  // Style de la barre
  const barStyle = useMemo(() => {
    const styles: React.CSSProperties = {};

    if (color) {
      styles.background = color;
    }

    if (height) {
      if (isHorizontal) {
        styles.height = typeof height === 'number' ? `${height}px` : height;
      } else {
        styles.width = typeof height === 'number' ? `${height}px` : height;
      }
    }

    if (width) {
      if (isHorizontal) {
        styles.width = typeof width === 'number' ? `${width}px` : width;
      } else {
        styles.height = typeof width === 'number' ? `${width}px` : width;
      }
    }

    if (radius) {
      styles.borderRadius = typeof radius === 'number' ? `${radius}px` : radius;
    }

    if (backgroundColor) {
      styles.backgroundColor = backgroundColor;
    }

    return styles;
  }, [color, height, width, radius, backgroundColor, isHorizontal]);

  // Animation du glow
  const glowClassName = glow ? 'relative overflow-visible' : '';

  return (
    <div
      className={cn(
        'relative overflow-hidden',
        isHorizontal ? 'w-full' : 'h-full min-h-[100px]',
        isHorizontal ? sizeClasses.height : 'w-[--progress-width]',
        shapeClasses,
        variantColors.bg,
        shadow && 'shadow-inner',
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
      style={{
        ...barStyle,
        '--progress-width': width || '1.5rem',
      } as React.CSSProperties}
      role="progressbar"
      aria-valuenow={indeterminate ? undefined : Math.round(value)}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuetext={indeterminate ? 'En cours...' : `${Math.round(percentage)}%`}
    >
      {/* Barre de progression */}
      {indeterminate ? (
        <div
          className={cn(
            'absolute inset-y-0 left-0',
            isHorizontal ? 'h-full' : 'w-full',
            variantColors.bar,
            gradient && 'bg-gradient-to-r from-brand-400 to-brand-600',
            striped && 'progress-striped',
            stripedAnimated && 'progress-striped-animated',
            glow && 'shadow-[0_0_20px_rgba(99,102,241,0.5)]',
            barClassName
          )}
          style={{
            width: isHorizontal ? '50%' : '100%',
            height: isHorizontal ? '100%' : '50%',
            animation: 'progress-indeterminate 1.5s ease-in-out infinite',
          }}
        />
      ) : (
        <motion.div
          className={cn(
            'absolute inset-y-0 left-0',
            isHorizontal ? 'h-full' : 'w-full',
            variantColors.bar,
            gradient && 'bg-gradient-to-r from-brand-400 to-brand-600',
            striped && 'progress-striped',
            stripedAnimated && 'progress-striped-animated',
            glow && 'shadow-[0_0_20px_rgba(99,102,241,0.5)]',
            barClassName
          )}
          initial={false}
          animate={{
            [isHorizontal ? 'width' : 'height']: `${percentage}%`,
          }}
          transition={{
            duration: animationDuration / 1000,
            ease: ANIMATION_TIMING_MAP[animation] || 'ease-in-out',
          }}
          style={{
            ...(isHorizontal ? { width: `${percentage}%` } : { height: `${percentage}%` }),
          }}
        />
      )}
    </div>
  );
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const Progress = forwardRef<HTMLDivElement, ProgressProps>(
  (props, ref) => {
    const {
      // Contrôle
      value: externalValue,
      defaultValue = 0,
      onValueChange,
      onComplete,

      // Apparence
      variant = 'default',
      size = 'md',
      shape = 'rounded',
      direction = 'horizontal',
      labelPosition = 'top',
      animation = 'ease-in-out',
      className,
      barClassName,
      containerClassName,
      labelClassName,
      valueClassName,

      // Contenu
      label,
      formatValue,
      icon,
      successIcon = <CheckCircleIcon className="h-5 w-5" />,
      errorIcon = <XCircleIcon className="h-5 w-5" />,
      showValue = true,
      showStatus = true,
      showStatusIcon = true,
      showSteps = false,
      showTimeRemaining = false,

      // États
      status: externalStatus,
      isLoading = false,
      indeterminate = false,
      disabled = false,

      // Valeurs
      min = 0,
      max = 100,
      successThreshold = 100,
      warningThreshold = 70,
      errorThreshold = 30,

      // Étapes
      steps = [],
      currentStep: externalCurrentStep,
      onStepChange,

      // Contrôle
      animationDuration = 300,
      delay = 0,
      autoIncrementInterval = 0,
      autoIncrement = false,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,

      // Avancé
      color,
      backgroundColor,
      height,
      width,
      radius,
      striped = false,
      stripedAnimated = false,
      shadow = false,
      glow = false,
      gradient = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const progressRef = useRef<HTMLDivElement>(null);
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const autoIncrementRef = useRef<NodeJS.Timeout | null>(null);
    const startTimeRef = useRef<number>(0);
    const uniqueId = useId();
    const progressId = id || `nexus-progress-${uniqueId}`;

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState(defaultValue);
    const [internalStatus, setInternalStatus] = useState<ProgressStatus>(
      externalStatus || 'idle'
    );
    const [elapsedTime, setElapsedTime] = useState(0);
    const [estimatedRemaining, setEstimatedRemaining] = useState<number | null>(null);
    const [currentStepIndex, setCurrentStepIndex] = useState(0);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue ?? internalValue;
    const status = externalStatus || internalStatus;
    const isControlled = externalValue !== undefined;
    const percentage = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
    const isComplete = percentage >= 100;
    const isError = status === 'error';
    const isWarning = status === 'warning';
    const isSuccess = status === 'complete' || isComplete;
    const isActive = status === 'active' || isLoading;
    const isPaused = status === 'paused';

    // Détermination de l'étape courante
    const currentStepId = useMemo(() => {
      if (externalCurrentStep) return externalCurrentStep;
      if (steps.length === 0) return undefined;

      // Trouver l'étape correspondant à la valeur actuelle
      const stepSize = 100 / steps.length;
      const stepIndex = Math.min(
        Math.floor(percentage / stepSize),
        steps.length - 1
      );
      return steps[stepIndex]?.id;
    }, [percentage, steps, externalCurrentStep]);

    const currentStep = steps.find((s) => s.id === currentStepId);

    // ========================================================================
    // FORMATAGE
    // ========================================================================

    const defaultFormatValue = useCallback((val: number) => {
      return `${Math.round(val)}%`;
    }, []);

    const formatValueFn = formatValue || defaultFormatValue;

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const setValue = useCallback((newValue: number) => {
      const clampedValue = Math.max(min, Math.min(max, newValue));

      if (isControlled) {
        onValueChange?.(clampedValue);
      } else {
        setInternalValue(clampedValue);
      }

      // Mettre à jour le statut
      if (clampedValue >= max) {
        setInternalStatus('complete');
        onComplete?.();
      } else if (clampedValue >= successThreshold) {
        setInternalStatus('complete');
      } else if (clampedValue >= warningThreshold) {
        setInternalStatus('warning');
      } else if (clampedValue >= errorThreshold) {
        setInternalStatus('active');
      } else {
        setInternalStatus('active');
      }
    }, [min, max, isControlled, onValueChange, onComplete, successThreshold, warningThreshold, errorThreshold]);

    // ========================================================================
    // AUTO-INCRÉMENTATION
    // ========================================================================

    const startAutoIncrement = useCallback(() => {
      if (autoIncrementRef.current) {
        clearInterval(autoIncrementRef.current);
      }

      if (!autoIncrement || disabled || isComplete) return;

      autoIncrementRef.current = setInterval(() => {
        setValue(value + 1);
      }, autoIncrementInterval || 100);
    }, [autoIncrement, autoIncrementInterval, disabled, isComplete, setValue, value]);

    const stopAutoIncrement = useCallback(() => {
      if (autoIncrementRef.current) {
        clearInterval(autoIncrementRef.current);
        autoIncrementRef.current = null;
      }
    }, []);

    // ========================================================================
    // STATUT
    // ========================================================================

    useEffect(() => {
      if (externalStatus) {
        setInternalStatus(externalStatus);
      }
    }, [externalStatus]);

    // ========================================================================
    // TEMPS RESTANT
    // ========================================================================

    useEffect(() => {
      if (!showTimeRemaining || isLoading || isComplete) return;

      if (isActive && value > 0) {
        const now = Date.now();
        if (startTimeRef.current === 0) {
          startTimeRef.current = now;
        }

        const elapsed = (now - startTimeRef.current) / 1000;
        setElapsedTime(elapsed);

        // Estimer le temps restant
        if (value > 0 && value < max) {
          const progress = (value - min) / (max - min);
          const estimatedTotal = elapsed / progress;
          const remaining = estimatedTotal - elapsed;
          setEstimatedRemaining(remaining);
        }
      } else if (isPaused) {
        // Garder le temps écoulé
      } else if (isComplete) {
        setEstimatedRemaining(0);
      }
    }, [value, min, max, isActive, isPaused, isComplete, isLoading, showTimeRemaining]);

    // ========================================================================
    // DÉMARRAGE / ARRÊT
    // ========================================================================

    useEffect(() => {
      if (isActive) {
        startAutoIncrement();
        startTimeRef.current = Date.now();
      } else {
        stopAutoIncrement();
      }

      return () => {
        stopAutoIncrement();
      };
    }, [isActive, startAutoIncrement, stopAutoIncrement]);

    // ========================================================================
    // CLEANUP
    // ========================================================================

    useEffect(() => {
      return () => {
        if (timerRef.current) clearTimeout(timerRef.current);
        if (autoIncrementRef.current) clearInterval(autoIncrementRef.current);
      };
    }, []);

    // ========================================================================
    // CONTEXT
    // ========================================================================

    const contextValue = useMemo<ProgressContextType>(
      () => ({
        value,
        status,
        size,
        variant,
        disabled,
        isLoading,
        setValue,
      }),
      [value, status, size, variant, disabled, isLoading, setValue]
    );

    // ========================================================================
    // RENDU DES ÉTAPES
    // ========================================================================

    const renderSteps = () => {
      if (!showSteps || steps.length === 0) return null;

      return (
        <div className="mt-4 flex items-center gap-2">
          {steps.map((step, index) => {
            const isActive = step.id === currentStepId;
            const isCompleted = index < steps.findIndex((s) => s.id === currentStepId);
            const stepStatus = step.status || (isCompleted ? 'complete' : isActive ? 'active' : 'idle');

            return (
              <div key={step.id} className="flex-1">
                <div
                  className={cn(
                    'flex items-center gap-2 rounded-lg p-2 transition-colors',
                    isActive && 'bg-brand-50 dark:bg-brand-900/20',
                    isCompleted && 'bg-green-50 dark:bg-green-900/20',
                    step.isOptional && 'border border-dashed border-gray-300 dark:border-gray-700'
                  )}
                >
                  <div className="flex-shrink-0">
                    {step.icon || (
                      <div
                        className={cn(
                          'flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium',
                          isCompleted && 'bg-green-500 text-white',
                          isActive && 'bg-brand-500 text-white',
                          stepStatus === 'idle' && 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400',
                          stepStatus === 'error' && 'bg-red-500 text-white',
                          stepStatus === 'warning' && 'bg-yellow-500 text-white'
                        )}
                      >
                        {isCompleted ? (
                          <CheckIcon className="h-3 w-3" />
                        ) : (
                          index + 1
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div
                      className={cn(
                        'text-sm font-medium',
                        isActive && 'text-brand-700 dark:text-brand-400',
                        isCompleted && 'text-green-700 dark:text-green-400',
                        stepStatus === 'idle' && 'text-gray-500 dark:text-gray-400'
                      )}
                    >
                      {step.label}
                    </div>
                    {step.description && (
                      <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                        {step.description}
                      </div>
                    )}
                  </div>
                  {step.isOptional && (
                    <Badge variant="outline" size="xs" className="ml-auto">
                      Optionnel
                    </Badge>
                  )}
                </div>
                {index < steps.length - 1 && (
                  <div className="ml-4 h-6 w-0.5 bg-gray-200 dark:bg-gray-700" />
                )}
              </div>
            );
          })}
        </div>
      );
    };

    // ========================================================================
    // RENDU DU TEMPS RESTANT
    // ========================================================================

    const renderTimeRemaining = () => {
      if (!showTimeRemaining || !isActive) return null;

      const formatTime = (seconds: number): string => {
        if (seconds < 60) return `${Math.round(seconds)}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
        return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
      };

      const elapsed = formatTime(elapsedTime);
      const remaining = estimatedRemaining !== null ? formatTime(estimatedRemaining) : '...';

      return (
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {elapsed} / {remaining}
        </span>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const variantColors = VARIANT_COLOR_MAP[variant] || VARIANT_COLOR_MAP.default;
    const sizeClasses = SIZE_MAP[size] || SIZE_MAP.md;
    const isHorizontal = direction === 'horizontal';

    // Conteneur principal
    const containerClasses = cn(
      'flex',
      isHorizontal ? 'flex-col' : 'flex-row items-center',
      labelPosition === 'top' && isHorizontal && 'flex-col',
      labelPosition === 'bottom' && isHorizontal && 'flex-col-reverse',
      labelPosition === 'left' && isHorizontal && 'flex-row items-center gap-3',
      labelPosition === 'right' && isHorizontal && 'flex-row-reverse items-center gap-3',
      labelPosition === 'inside' && isHorizontal && 'relative',
      containerClassName
    );

    // Libellé
    const renderLabel = () => {
      if (labelPosition === 'none') return null;

      const labelContent = (
        <div className={cn('flex items-center gap-2', labelClassName)}>
          {icon && <span className="text-gray-500 dark:text-gray-400">{icon}</span>}
          {label && <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{label}</span>}
          {showStatus && (
            <Badge
              variant={
                status === 'complete' ? 'success' :
                status === 'error' ? 'danger' :
                status === 'warning' ? 'warning' :
                'default'
              }
              size="sm"
              className="capitalize"
            >
              {status}
            </Badge>
          )}
          {showStatusIcon && status !== 'idle' && (
            <span className={cn('flex-shrink-0', STATUS_COLOR_MAP[status])}>
              {STATUS_ICON_MAP[status]}
            </span>
          )}
        </div>
      );

      if (labelPosition === 'inside') {
        return (
          <div className="absolute inset-0 flex items-center justify-between px-4 z-10">
            <div className="flex items-center gap-2">
              {labelContent}
            </div>
            {showValue && (
              <span className={cn('font-mono', valueClassName || variantColors.text)}>
                {formatValueFn(value)}
              </span>
            )}
          </div>
        );
      }

      return (
        <div className={cn('flex items-center justify-between w-full', sizeClasses.gap)}>
          {labelContent}
          <div className="flex items-center gap-2">
            {showValue && (
              <span className={cn('font-mono text-sm', valueClassName || variantColors.text)}>
                {formatValueFn(value)}
              </span>
            )}
            {renderTimeRemaining()}
          </div>
        </div>
      );
    };

    // Barre de progression
    const renderBar = () => {
      return (
        <ProgressBar
          value={value}
          min={min}
          max={max}
          variant={variant}
          size={size}
          shape={shape}
          direction={direction}
          animation={animation}
          animationDuration={animationDuration}
          indeterminate={indeterminate}
          disabled={disabled}
          className={barClassName}
          barClassName={barClassName}
          color={color}
          backgroundColor={backgroundColor}
          height={height}
          width={width}
          radius={radius}
          striped={striped}
          stripedAnimated={stripedAnimated}
          shadow={shadow}
          glow={glow}
          gradient={gradient}
        />
      );
    };

    return (
      <ProgressContext.Provider value={contextValue}>
        <div
          ref={ref}
          id={progressId}
          className={cn('w-full', className)}
          aria-label={ariaLabel}
          aria-describedby={ariaDescribedby}
        >
          <div className={containerClasses}>
            {/* Libellé en haut */}
            {(labelPosition === 'top' || labelPosition === 'left') && renderLabel()}

            {/* Barre de progression */}
            <div className="flex-1 w-full">
              {renderBar()}
            </div>

            {/* Libellé en bas */}
            {(labelPosition === 'bottom' || labelPosition === 'right') && renderLabel()}
          </div>

          {/* Étapes */}
          {renderSteps()}

          {/* Affichage du statut */}
          {showStatus && status && (
            <div className="mt-2 flex items-center gap-2 text-sm">
              <span className={cn('capitalize', STATUS_COLOR_MAP[status])}>
                {status}
              </span>
              {isComplete && (
                <span className="text-green-600 dark:text-green-400">
                  {successIcon}
                </span>
              )}
              {isError && (
                <span className="text-red-600 dark:text-red-400">
                  {errorIcon}
                </span>
              )}
            </div>
          )}
        </div>
      </ProgressContext.Provider>
    );
  }
);

Progress.displayName = 'Progress';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- Progress.Circle ---
interface ProgressCircleProps {
  value?: number;
  size?: ProgressSize;
  variant?: ProgressVariant;
  status?: ProgressStatus;
  showValue?: boolean;
  formatValue?: (value: number) => string;
  className?: string;
  strokeWidth?: number;
  color?: string;
  backgroundColor?: string;
}

export const ProgressCircle: React.FC<ProgressCircleProps> = ({
  value = 0,
  size = 'md',
  variant = 'default',
  status = 'idle',
  showValue = true,
  formatValue,
  className,
  strokeWidth = 8,
  color,
  backgroundColor,
}) => {
  const percentage = Math.max(0, Math.min(100, value));

  const sizeMap = {
    xs: 40,
    sm: 56,
    md: 72,
    lg: 96,
    xl: 120,
  };

  const fontSizeMap = {
    xs: 'text-xs',
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-xl',
    xl: 'text-2xl',
  };

  const variantColors = VARIANT_COLOR_MAP[variant] || VARIANT_COLOR_MAP.default;
  const statusColors = {
    idle: 'text-gray-400',
    active: 'text-brand-500',
    paused: 'text-yellow-500',
    complete: 'text-green-500',
    error: 'text-red-500',
    warning: 'text-yellow-500',
  };

  const radius = sizeMap[size] / 2 - strokeWidth / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;

  const defaultFormat = (val: number) => `${Math.round(val)}%`;
  const format = formatValue || defaultFormat;

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)}>
      <svg
        className="transform -rotate-90"
        width={sizeMap[size]}
        height={sizeMap[size]}
        viewBox={`0 0 ${sizeMap[size]} ${sizeMap[size]}`}
      >
        {/* Cercle de fond */}
        <circle
          className="text-gray-200 dark:text-gray-700"
          cx={sizeMap[size] / 2}
          cy={sizeMap[size] / 2}
          r={radius}
          fill="none"
          stroke={backgroundColor || 'currentColor'}
          strokeWidth={strokeWidth}
          opacity={0.3}
        />
        {/* Cercle de progression */}
        <circle
          className={cn(
            'transition-all duration-300 ease-in-out',
            variantColors.bar,
            color ? '' : ''
          )}
          cx={sizeMap[size] / 2}
          cy={sizeMap[size] / 2}
          r={radius}
          fill="none"
          stroke={color || 'currentColor'}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{
            transition: 'stroke-dashoffset 0.5s ease-in-out',
          }}
        />
      </svg>

      {showValue && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={cn('font-semibold', fontSizeMap[size], statusColors[status])}>
            {format(value)}
          </span>
        </div>
      )}
    </div>
  );
};

// --- Progress.Donut ---
interface ProgressDonutProps extends ProgressCircleProps {
  thickness?: number;
}

export const ProgressDonut: React.FC<ProgressDonutProps> = (props) => {
  return <ProgressCircle {...props} strokeWidth={props.thickness || 12} />;
};

// ============================================================================
// HOOKS
// ============================================================================

export const useProgress = (initialValue = 0, options?: {
  min?: number;
  max?: number;
  autoIncrement?: boolean;
  interval?: number;
  onComplete?: () => void;
}) => {
  const [value, setValue] = useState(initialValue);
  const [status, setStatus] = useState<ProgressStatus>('idle');
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const min = options?.min || 0;
  const max = options?.max || 100;

  const start = useCallback(() => {
    setStatus('active');
    if (options?.autoIncrement) {
      timerRef.current = setInterval(() => {
        setValue((prev) => {
          const next = Math.min(prev + 1, max);
          if (next >= max) {
            setStatus('complete');
            options?.onComplete?.();
            if (timerRef.current) clearInterval(timerRef.current);
          }
          return next;
        });
      }, options?.interval || 100);
    }
  }, [max, options]);

  const pause = useCallback(() => {
    setStatus('paused');
    if (timerRef.current) clearInterval(timerRef.current);
  }, []);

  const resume = useCallback(() => {
    setStatus('active');
    if (options?.autoIncrement) {
      timerRef.current = setInterval(() => {
        setValue((prev) => {
          const next = Math.min(prev + 1, max);
          if (next >= max) {
            setStatus('complete');
            options?.onComplete?.();
            if (timerRef.current) clearInterval(timerRef.current);
          }
          return next;
        });
      }, options?.interval || 100);
    }
  }, [max, options]);

  const reset = useCallback(() => {
    setValue(min);
    setStatus('idle');
    if (timerRef.current) clearInterval(timerRef.current);
  }, [min]);

  const complete = useCallback(() => {
    setValue(max);
    setStatus('complete');
    if (timerRef.current) clearInterval(timerRef.current);
    options?.onComplete?.();
  }, [max, options]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  return {
    value,
    setValue,
    status,
    setStatus,
    start,
    pause,
    resume,
    reset,
    complete,
    isActive: status === 'active',
    isPaused: status === 'paused',
    isComplete: status === 'complete',
    isError: status === 'error',
    percentage: ((value - min) / (max - min)) * 100,
  };
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(Progress, {
  Circle: ProgressCircle,
  Donut: ProgressDonut,
});

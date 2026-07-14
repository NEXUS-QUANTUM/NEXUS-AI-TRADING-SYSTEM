// apps/web/src/components/forms/layouts/FormWizardLayout.tsx
'use client';

import React, {
  ReactNode,
  forwardRef,
  Ref,
  useState,
  useCallback,
  useEffect,
  useRef,
  Children,
  isValidElement,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronDownIcon,
  ChevronUpIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
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
  ArrowLeftIcon,
  ArrowRightIcon,
  PlayIcon,
  PauseIcon,
  StopIcon,
  RocketLaunchIcon,
  SparklesIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/common/Button';
import { Badge } from '@/components/common/Badge';
import { Separator } from '@/components/common/Separator';
import { Progress } from '@/components/common/Progress';
import { Tooltip } from '@/components/common/Tooltip';
import { ScrollArea } from '@/components/common/ScrollArea';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type WizardStep = {
  /** Identifiant de l'étape */
  id: string;
  /** Titre de l'étape */
  title: string;
  /** Description de l'étape */
  description?: string;
  /** Icône de l'étape */
  icon?: React.ReactNode;
  /** Contenu de l'étape */
  content: ReactNode;
  /** Statut de l'étape */
  status?: 'idle' | 'active' | 'completed' | 'error' | 'warning' | 'info' | 'skipped';
  /** Désactiver l'étape */
  disabled?: boolean;
  /** Rendre l'étape optionnelle */
  optional?: boolean;
  /** Valider l'étape */
  validate?: () => boolean | Promise<boolean>;
  /** Classe additionnelle */
  className?: string;
};

export type WizardVariant = 'default' | 'cards' | 'minimal' | 'stepper' | 'timeline' | 'compact';
export type WizardSize = 'sm' | 'md' | 'lg' | 'xl';
export type WizardStatus = 'idle' | 'loading' | 'success' | 'error' | 'warning' | 'info';
export type WizardAnimation = 'fade' | 'slide' | 'scale' | 'bounce' | 'none';
export type WizardNavigation = 'top' | 'bottom' | 'both' | 'none';
export type WizardStepDisplay = 'numbers' | 'icons' | 'both' | 'none';

export interface FormWizardLayoutProps {
  // --- Contrôle ---
  /** Étapes du wizard */
  steps: WizardStep[];
  /** Étape active (contrôlée) */
  activeStep?: string;
  /** Étape active par défaut */
  defaultActiveStep?: string;
  /** Callback de changement d'étape */
  onStepChange?: (stepId: string) => void;
  /** Callback de completion */
  onComplete?: () => void;

  // --- Apparence ---
  /** Variante du wizard */
  variant?: WizardVariant;
  /** Taille du wizard */
  size?: WizardSize;
  /** Statut du wizard */
  status?: WizardStatus;
  /** Animation de transition */
  animation?: WizardAnimation;
  /** Position de la navigation */
  navigation?: WizardNavigation;
  /** Affichage des étapes */
  stepDisplay?: WizardStepDisplay;
  /** Afficher la barre de progression */
  showProgress?: boolean;
  /** Afficher les badges de statut */
  showStatusBadges?: boolean;
  /** Afficher les icônes */
  showIcons?: boolean;
  /** Afficher les descriptions */
  showDescriptions?: boolean;
  /** Afficher le compteur d'étapes */
  showStepCount?: boolean;
  /** Afficher la navigation rapide */
  showQuickNav?: boolean;
  /** Afficher les actions */
  showActions?: boolean;
  /** Classes additionnelles */
  className?: string;
  /** Classe pour la barre de progression */
  progressClassName?: string;
  /** Classe pour la navigation */
  navigationClassName?: string;
  /** Classe pour le contenu */
  contentClassName?: string;
  /** Classe pour les étapes */
  stepClassName?: string;
  /** Classe pour l'étape active */
  activeStepClassName?: string;

  // --- Comportement ---
  /** Désactiver le wizard */
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
  /** Validation automatique avant de changer d'étape */
  autoValidate?: boolean;
  /** Sauvegarder la progression */
  saveProgress?: boolean;
  /** Clé de sauvegarde */
  saveKey?: string;

  // --- Actions ---
  /** Callback de soumission finale */
  onSubmit?: () => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de réinitialisation */
  onReset?: () => void;
  /** Callback de validation d'étape */
  onStepValidate?: (stepId: string) => boolean | Promise<boolean>;
  /** Callback d'entrée d'étape */
  onStepEnter?: (stepId: string) => void;
  /** Callback de sortie d'étape */
  onStepLeave?: (stepId: string) => void;
  /** Callback de saut d'étape (optionnelle) */
  onStepSkip?: (stepId: string) => void;

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

const VARIANT_MAP: Record<WizardVariant, string> = {
  default: 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl',
  cards: 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg',
  minimal: 'bg-transparent',
  stepper: 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl',
  timeline: 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl',
  compact: 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl',
};

const STEP_VARIANT_MAP: Record<WizardVariant, string> = {
  default: 'flex items-center gap-3 p-4 border-b border-gray-200 dark:border-gray-700 last:border-0',
  cards: 'flex items-center gap-3 p-4 border-b border-gray-200 dark:border-gray-700 last:border-0',
  minimal: 'flex items-center gap-3 p-2',
  stepper: 'flex items-center gap-3 p-4 border-b border-gray-200 dark:border-gray-700 last:border-0',
  timeline: 'flex items-start gap-4 p-4 border-l-2 border-gray-200 dark:border-gray-700 pl-6',
  compact: 'flex items-center gap-2 p-2 border-b border-gray-200 dark:border-gray-700 last:border-0',
};

const SIZE_MAP: Record<WizardSize, { padding: string; fontSize: string; gap: string }> = {
  sm: { padding: 'p-3', fontSize: 'text-sm', gap: 'gap-2' },
  md: { padding: 'p-4', fontSize: 'text-base', gap: 'gap-3' },
  lg: { padding: 'p-6', fontSize: 'text-lg', gap: 'gap-4' },
  xl: { padding: 'p-8', fontSize: 'text-xl', gap: 'gap-5' },
};

const STATUS_MAP: Record<WizardStatus, { color: string; icon: React.ReactNode }> = {
  idle: {
    color: 'text-gray-500 dark:text-gray-400',
    icon: <InformationCircleIcon className="h-5 w-5" />,
  },
  loading: {
    color: 'text-brand-500',
    icon: <ArrowPathIcon className="h-5 w-5 animate-spin" />,
  },
  success: {
    color: 'text-green-500',
    icon: <CheckCircleIcon className="h-5 w-5" />,
  },
  error: {
    color: 'text-red-500',
    icon: <ExclamationCircleIcon className="h-5 w-5" />,
  },
  warning: {
    color: 'text-yellow-500',
    icon: <ExclamationTriangleIcon className="h-5 w-5" />,
  },
  info: {
    color: 'text-blue-500',
    icon: <InformationCircleIcon className="h-5 w-5" />,
  },
};

const STEP_STATUS_MAP: Record<NonNullable<WizardStep['status']>, { color: string; icon: React.ReactNode; bg: string }> = {
  idle: {
    color: 'text-gray-400 dark:text-gray-500',
    icon: <InformationCircleIcon className="h-4 w-4" />,
    bg: 'bg-gray-200 dark:bg-gray-700',
  },
  active: {
    color: 'text-brand-500',
    icon: <PlayIcon className="h-4 w-4" />,
    bg: 'bg-brand-500',
  },
  completed: {
    color: 'text-green-500',
    icon: <CheckIcon className="h-4 w-4" />,
    bg: 'bg-green-500',
  },
  error: {
    color: 'text-red-500',
    icon: <ExclamationCircleIcon className="h-4 w-4" />,
    bg: 'bg-red-500',
  },
  warning: {
    color: 'text-yellow-500',
    icon: <ExclamationTriangleIcon className="h-4 w-4" />,
    bg: 'bg-yellow-500',
  },
  info: {
    color: 'text-blue-500',
    icon: <InformationCircleIcon className="h-4 w-4" />,
    bg: 'bg-blue-500',
  },
  skipped: {
    color: 'text-gray-400 dark:text-gray-500',
    icon: <MinusIcon className="h-4 w-4" />,
    bg: 'bg-gray-300 dark:bg-gray-600',
  },
};

const ANIMATION_MAP: Record<WizardAnimation, {
  initial: { opacity?: number; x?: string | number; y?: string | number; scale?: number };
  animate: { opacity?: number; x?: string | number; y?: string | number; scale?: number };
  exit: { opacity?: number; x?: string | number; y?: string | number; scale?: number };
}> = {
  fade: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
  },
  slide: {
    initial: { opacity: 0, x: 30 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -30 },
  },
  scale: {
    initial: { opacity: 0, scale: 0.95 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.95 },
  },
  bounce: {
    initial: { opacity: 0, y: 20, scale: 0.9 },
    animate: { opacity: 1, y: 0, scale: 1 },
    exit: { opacity: 0, y: -20, scale: 0.9 },
  },
  none: {
    initial: { opacity: 1 },
    animate: { opacity: 1 },
    exit: { opacity: 1 },
  },
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const FormWizardLayout = forwardRef<HTMLDivElement, FormWizardLayoutProps>(
  (props, ref) => {
    const {
      // Contrôle
      steps,
      activeStep: externalActiveStep,
      defaultActiveStep,
      onStepChange,
      onComplete,

      // Apparence
      variant = 'default',
      size = 'md',
      status = 'idle',
      animation = 'slide',
      navigation = 'bottom',
      stepDisplay = 'both',
      showProgress = true,
      showStatusBadges = true,
      showIcons = true,
      showDescriptions = true,
      showStepCount = true,
      showQuickNav = false,
      showActions = true,
      className,
      progressClassName,
      navigationClassName,
      contentClassName,
      stepClassName,
      activeStepClassName,

      // Comportement
      disabled = false,
      isLoading = false,
      error = null,
      success = null,
      info = null,
      warning = null,
      progress: externalProgress,
      autoValidate = true,
      saveProgress = false,
      saveKey = 'wizard_progress',

      // Actions
      onSubmit,
      onCancel,
      onReset,
      onStepValidate,
      onStepEnter,
      onStepLeave,
      onStepSkip,

      // Accessibilité
      ariaLabel = 'Assistant étape par étape',
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
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalActiveStep, setInternalActiveStep] = useState<string>(
      defaultActiveStep || (steps.length > 0 ? steps[0].id : '')
    );
    const [stepStatuses, setStepStatuses] = useState<Record<string, WizardStep['status']>>(() => {
      const statuses: Record<string, WizardStep['status']> = {};
      steps.forEach((step, index) => {
        statuses[step.id] = index === 0 ? 'active' : 'idle';
      });
      return statuses;
    });
    const [isValidating, setIsValidating] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const activeStep = externalActiveStep !== undefined ? externalActiveStep : internalActiveStep;
    const isControlled = externalActiveStep !== undefined;

    const activeStepIndex = steps.findIndex(s => s.id === activeStep);
    const currentStep = steps[activeStepIndex];
    const isFirstStep = activeStepIndex === 0;
    const isLastStep = activeStepIndex === steps.length - 1;

    const completedSteps = steps.filter(s => stepStatuses[s.id] === 'completed').length;
    const totalSteps = steps.length;
    const progressValue = externalProgress !== undefined ? externalProgress : (totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0);

    const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
    const variantStyles = VARIANT_MAP[variant] || VARIANT_MAP.default;
    const stepVariantStyles = STEP_VARIANT_MAP[variant] || STEP_VARIANT_MAP.default;
    const statusMap = STATUS_MAP[status] || STATUS_MAP.idle;
    const animationStyles = ANIMATION_MAP[animation] || ANIMATION_MAP.slide;

    const hasStatusMessage = error || success || info || warning;
    const statusMessage = error || success || info || warning;
    const statusType = error ? 'error' : success ? 'success' : warning ? 'warning' : info ? 'info' : null;
    const statusColor = statusType ? STATUS_MAP[statusType as WizardStatus]?.color : statusMap.color;

    const showTopNav = navigation === 'top' || navigation === 'both';
    const showBottomNav = navigation === 'bottom' || navigation === 'both';
    const showNav = navigation !== 'none';

    // ========================================================================
    // SAUVEGARDE DE LA PROGRESSION
    // ========================================================================

    useEffect(() => {
      if (saveProgress && typeof window !== 'undefined') {
        try {
          localStorage.setItem(saveKey, JSON.stringify({
            activeStep,
            stepStatuses,
            timestamp: Date.now(),
          }));
        } catch (error) {
          console.error('Erreur de sauvegarde:', error);
        }
      }
    }, [saveProgress, saveKey, activeStep, stepStatuses]);

    useEffect(() => {
      if (saveProgress && typeof window !== 'undefined') {
        try {
          const saved = localStorage.getItem(saveKey);
          if (saved) {
            const data = JSON.parse(saved);
            // Vérifier si les données sont encore valides
            const stepExists = steps.some(s => s.id === data.activeStep);
            if (stepExists) {
              setInternalActiveStep(data.activeStep);
              setStepStatuses(data.stepStatuses);
            }
          }
        } catch (error) {
          console.error('Erreur de chargement:', error);
        }
      }
    }, [saveProgress, saveKey, steps]);

    // ========================================================================
    // CHANGEMENT D'ÉTAPE
    // ========================================================================

    const setActiveStep = useCallback((stepId: string) => {
      if (isControlled) {
        if (onStepChange) onStepChange(stepId);
      } else {
        setInternalActiveStep(stepId);
        if (onStepChange) onStepChange(stepId);
      }
    }, [isControlled, onStepChange]);

    const goToStep = useCallback(async (stepId: string) => {
      const step = steps.find(s => s.id === stepId);
      if (!step || step.disabled || disabled) return false;

      // Validation automatique avant de changer d'étape
      if (autoValidate && currentStep) {
        const isValid = await validateStep(currentStep.id);
        if (!isValid) {
          toast({
            title: 'Erreur de validation',
            description: `L'étape "${currentStep.title}" contient des erreurs`,
            variant: 'destructive',
          });
          return false;
        }
      }

      // Marquer l'étape courante comme complétée si on avance
      if (steps.findIndex(s => s.id === stepId) > activeStepIndex) {
        setStepStatuses(prev => ({
          ...prev,
          [currentStep.id]: 'completed',
        }));
      }

      setActiveStep(stepId);
      return true;
    }, [steps, currentStep, activeStepIndex, autoValidate, disabled, setActiveStep, toast]);

    const goToNextStep = useCallback(async () => {
      if (isLastStep) {
        // Si c'est la dernière étape, compléter le wizard
        if (onComplete) onComplete();
        setStepStatuses(prev => ({
          ...prev,
          [currentStep.id]: 'completed',
        }));
        return;
      }

      const nextStep = steps[activeStepIndex + 1];
      if (nextStep && !nextStep.disabled) {
        await goToStep(nextStep.id);
      }
    }, [isLastStep, currentStep, steps, activeStepIndex, goToStep, onComplete]);

    const goToPreviousStep = useCallback(async () => {
      if (isFirstStep) return;
      const prevStep = steps[activeStepIndex - 1];
      if (prevStep && !prevStep.disabled) {
        await goToStep(prevStep.id);
      }
    }, [isFirstStep, steps, activeStepIndex, goToStep]);

    const skipStep = useCallback(async () => {
      if (!currentStep?.optional) {
        toast({
          title: 'Étape obligatoire',
          description: 'Cette étape ne peut pas être sautée',
          variant: 'destructive',
        });
        return;
      }

      setStepStatuses(prev => ({
        ...prev,
        [currentStep.id]: 'skipped',
      }));

      if (onStepSkip) onStepSkip(currentStep.id);
      await goToNextStep();
    }, [currentStep, goToNextStep, onStepSkip, toast]);

    // ========================================================================
    // VALIDATION D'ÉTAPE
    // ========================================================================

    const validateStep = useCallback(async (stepId: string): Promise<boolean> => {
      const step = steps.find(s => s.id === stepId);
      if (!step) return true;

      setIsValidating(true);

      try {
        // Validation personnalisée
        if (onStepValidate) {
          const result = await onStepValidate(stepId);
          if (!result) {
            setStepStatuses(prev => ({
              ...prev,
              [stepId]: 'error',
            }));
            return false;
          }
        }

        // Validation intégrée à l'étape
        if (step.validate) {
          const result = await step.validate();
          if (!result) {
            setStepStatuses(prev => ({
              ...prev,
              [stepId]: 'error',
            }));
            return false;
          }
        }

        setStepStatuses(prev => ({
          ...prev,
          [stepId]: prev[stepId] === 'error' ? 'idle' : prev[stepId],
        }));

        return true;
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Erreur de validation';
        setStepStatuses(prev => ({
          ...prev,
          [stepId]: 'error',
        }));
        toast({
          title: 'Erreur de validation',
          description: errorMessage,
          variant: 'destructive',
        });
        return false;
      } finally {
        setIsValidating(false);
      }
    }, [steps, onStepValidate, toast]);

    // ========================================================================
    // RÉINITIALISATION
    // ========================================================================

    const resetWizard = useCallback(() => {
      if (onReset) onReset();
      setInternalActiveStep(steps[0]?.id || '');
      const statuses: Record<string, WizardStep['status']> = {};
      steps.forEach((step, index) => {
        statuses[step.id] = index === 0 ? 'active' : 'idle';
      });
      setStepStatuses(statuses);
    }, [steps, onReset]);

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

    // ========================================================================
    // RENDU DE LA BARRE DE PROGRESSION
    // ========================================================================

    const renderProgress = () => {
      if (!showProgress) return null;

      return (
        <div className={cn('mb-4', progressClassName)}>
          <Progress
            value={progressValue}
            className="h-2"
            variant={
              progressValue >= 100 ? 'success' :
              progressValue >= 70 ? 'info' :
              progressValue >= 30 ? 'warning' :
              'default'
            }
          />
          <div className="mt-1 flex justify-between text-xs text-gray-500 dark:text-gray-400">
            <span>
              {completedSteps} / {totalSteps} étapes
              {currentStep?.optional && ' (optionnelle)'}
            </span>
            <span>{Math.round(progressValue)}%</span>
          </div>
        </div>
      );
    };

    // ========================================================================
    // RENDU DES ÉTAPES (navigation)
    // ========================================================================

    const renderSteps = () => {
      return (
        <div className="space-y-1">
          {steps.map((step, index) => {
            const isActive = step.id === activeStep;
            const status = stepStatuses[step.id] || 'idle';
            const statusStyles = STEP_STATUS_MAP[status] || STEP_STATUS_MAP.idle;
            const isCompleted = status === 'completed';
            const isSkipped = status === 'skipped';
            const isError = status === 'error';

            const stepNumber = index + 1;
            const displayNumber = stepDisplay === 'numbers' || stepDisplay === 'both';
            const displayIcon = stepDisplay === 'icons' || stepDisplay === 'both';

            return (
              <button
                key={step.id}
                type="button"
                className={cn(
                  'w-full text-left transition-all',
                  stepVariantStyles,
                  isActive && 'bg-gray-50 dark:bg-gray-800/50',
                  isCompleted && 'bg-green-50 dark:bg-green-900/10',
                  isError && 'bg-red-50 dark:bg-red-900/10',
                  isSkipped && 'opacity-50',
                  step.disabled && 'opacity-50 cursor-not-allowed',
                  stepClassName,
                  isActive && activeStepClassName
                )}
                onClick={() => {
                  if (!step.disabled && !disabled) {
                    goToStep(step.id);
                  }
                }}
                disabled={step.disabled || disabled}
              >
                <div className="flex items-center gap-3">
                  {/* Indicateur d'étape */}
                  <div className="flex-shrink-0">
                    {displayNumber && !displayIcon && (
                      <div className={cn(
                        'flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium transition-all',
                        isActive && 'bg-brand-500 text-white',
                        isCompleted && 'bg-green-500 text-white',
                        isError && 'bg-red-500 text-white',
                        isSkipped && 'bg-gray-300 text-gray-500 dark:bg-gray-600',
                        !isActive && !isCompleted && !isError && !isSkipped && 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                      )}>
                        {isCompleted ? <CheckIcon className="h-4 w-4" /> : stepNumber}
                      </div>
                    )}
                    {displayIcon && step.icon && (
                      <div className={cn(
                        'flex h-8 w-8 items-center justify-center rounded-full transition-all',
                        isActive && 'bg-brand-500 text-white',
                        isCompleted && 'bg-green-500 text-white',
                        isError && 'bg-red-500 text-white',
                        isSkipped && 'bg-gray-300 text-gray-500 dark:bg-gray-600',
                        !isActive && !isCompleted && !isError && !isSkipped && 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                      )}>
                        {isCompleted ? <CheckIcon className="h-4 w-4" /> : step.icon}
                      </div>
                    )}
                    {displayNumber && displayIcon && (
                      <div className={cn(
                        'flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium transition-all',
                        isActive && 'bg-brand-500 text-white',
                        isCompleted && 'bg-green-500 text-white',
                        isError && 'bg-red-500 text-white',
                        isSkipped && 'bg-gray-300 text-gray-500 dark:bg-gray-600',
                        !isActive && !isCompleted && !isError && !isSkipped && 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                      )}>
                        {isCompleted ? <CheckIcon className="h-4 w-4" /> : stepNumber}
                      </div>
                    )}
                  </div>

                  {/* Titre et description */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        'font-medium',
                        isActive && 'text-brand-700 dark:text-brand-400',
                        isCompleted && 'text-green-700 dark:text-green-400',
                        isError && 'text-red-700 dark:text-red-400',
                        isSkipped && 'text-gray-500 dark:text-gray-400'
                      )}>
                        {step.title}
                      </span>
                      {step.optional && (
                        <Badge variant="outline" size="xs" className="text-gray-400">
                          Optionnel
                        </Badge>
                      )}
                      {showStatusBadges && status !== 'idle' && status !== 'active' && (
                        <span className={statusStyles.color}>
                          {statusStyles.icon}
                        </span>
                      )}
                    </div>
                    {showDescriptions && step.description && (
                      <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
                        {step.description}
                      </p>
                    )}
                  </div>

                  {/* Statut */}
                  {isActive && (
                    <span className="flex-shrink-0 text-xs text-brand-500">
                      En cours
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      );
    };

    // ========================================================================
    // RENDU DU STATUT GLOBAL
    // ========================================================================

    const renderStatus = () => {
      if (!hasStatusMessage) return null;

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
    // RENDU DE LA NAVIGATION
    // ========================================================================

    const renderNavigation = (position: 'top' | 'bottom') => {
      if (!showNav) return null;
      if (position === 'top' && !showTopNav) return null;
      if (position === 'bottom' && !showBottomNav) return null;

      const isTop = position === 'top';

      return (
        <div
          className={cn(
            'flex items-center justify-between gap-3',
            isTop ? 'border-b border-gray-200 dark:border-gray-700 pb-4 mb-4' : 'border-t border-gray-200 dark:border-gray-700 pt-4 mt-4',
            navigationClassName
          )}
        >
          {/* Navigation rapide */}
          {showQuickNav && (
            <div className="flex items-center gap-1">
              <Tooltip content="Première étape">
                <button
                  type="button"
                  className="rounded-lg p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
                  onClick={() => goToStep(steps[0]?.id || '')}
                  disabled={isFirstStep || disabled || isLoading}
                >
                  <ChevronLeftIcon className="h-4 w-4" />
                  <ChevronLeftIcon className="h-4 w-4 -ml-2" />
                </button>
              </Tooltip>
              <Tooltip content="Étape précédente">
                <button
                  type="button"
                  className="rounded-lg p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
                  onClick={goToPreviousStep}
                  disabled={isFirstStep || disabled || isLoading}
                >
                  <ChevronLeftIcon className="h-4 w-4" />
                </button>
              </Tooltip>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {activeStepIndex + 1} / {totalSteps}
              </span>
              <Tooltip content="Étape suivante">
                <button
                  type="button"
                  className="rounded-lg p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
                  onClick={goToNextStep}
                  disabled={isLastStep || disabled || isLoading}
                >
                  <ChevronRightIcon className="h-4 w-4" />
                </button>
              </Tooltip>
              <Tooltip content="Dernière étape">
                <button
                  type="button"
                  className="rounded-lg p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
                  onClick={() => goToStep(steps[steps.length - 1]?.id || '')}
                  disabled={isLastStep || disabled || isLoading}
                >
                  <ChevronRightIcon className="h-4 w-4" />
                  <ChevronRightIcon className="h-4 w-4 -ml-2" />
                </button>
              </Tooltip>
            </div>
          )}

          {/* Actions */}
          {showActions && (
            <div className="flex items-center gap-2">
              {currentStep?.optional && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={skipStep}
                  disabled={disabled || isLoading}
                >
                  <MinusIcon className="h-4 w-4 mr-1" />
                  Sauter
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
              {onReset && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={resetWizard}
                  disabled={disabled || isLoading}
                >
                  Réinitialiser
                </Button>
              )}
              {isLastStep ? (
                <Button
                  type="submit"
                  variant="primary"
                  onClick={() => {
                    if (onComplete) onComplete();
                    if (onSubmit) onSubmit();
                  }}
                  disabled={disabled || isLoading}
                  isLoading={isLoading}
                >
                  {isLoading ? 'Finalisation...' : 'Terminer'}
                  <RocketLaunchIcon className="ml-2 h-4 w-4" />
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="primary"
                  onClick={goToNextStep}
                  disabled={disabled || isLoading}
                  isLoading={isValidating}
                >
                  {isValidating ? 'Validation...' : 'Suivant'}
                  <ArrowRightIcon className="ml-2 h-4 w-4" />
                </Button>
              )}
            </div>
          )}
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

      if (!currentStep) {
        return (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <ExclamationTriangleIcon className="h-12 w-12" />
            <p className="mt-3 text-sm">Étape non trouvée</p>
          </div>
        );
      }

      return (
        <AnimatePresence mode="wait">
          <motion.div
            key={activeStep}
            initial={!disableAnimations ? animationStyles.initial : {}}
            animate={!disableAnimations ? animationStyles.animate : {}}
            exit={!disableAnimations ? animationStyles.exit : {}}
            transition={{ duration: 0.3 }}
            className="flex-1"
          >
            {currentStep.content}
          </motion.div>
        </AnimatePresence>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    return (
      <div
        ref={ref}
        id={id}
        className={cn(
          'relative',
          variantStyles,
          sizeStyles.padding,
          className
        )}
        aria-label={ariaLabel}
        role="group"
      >
        {/* Barre de progression */}
        {renderProgress()}

        {/* Statut */}
        {renderStatus()}

        {/* Navigation supérieure */}
        {renderNavigation('top')}

        {/* Contenu principal */}
        <div className="flex flex-col md:flex-row gap-6">
          {/* Liste des étapes */}
          {variant !== 'compact' && (
            <div className="md:w-64 flex-shrink-0">
              <ScrollArea className="max-h-[400px]">
                {renderSteps()}
              </ScrollArea>
            </div>
          )}

          {/* Contenu */}
          <div ref={contentRef} className="flex-1 min-w-0">
            <div className={cn('min-h-[200px]', contentClassName)}>
              {renderContent()}
            </div>
          </div>
        </div>

        {/* Navigation inférieure */}
        {renderNavigation('bottom')}
      </div>
    );
  }
);

FormWizardLayout.displayName = 'FormWizardLayout';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- FormWizardLayout.Step ---
interface WizardStepProps extends WizardStep {
  children?: ReactNode;
}

export const WizardStep: React.FC<WizardStepProps> = ({
  id,
  title,
  description,
  icon,
  content,
  status,
  disabled,
  optional,
  validate,
  className,
  children,
}) => {
  return (
    <div className={cn('hidden', className)}>
      {content || children}
    </div>
  );
};

// --- FormWizardLayout.Content ---
interface WizardContentProps {
  children: ReactNode;
  className?: string;
}

export const WizardContent: React.FC<WizardContentProps> = ({
  children,
  className,
}) => {
  return (
    <div className={cn('p-4', className)}>
      {children}
    </div>
  );
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(FormWizardLayout, {
  Step: WizardStep,
  Content: WizardContent,
});

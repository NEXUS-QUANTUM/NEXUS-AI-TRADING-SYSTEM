// apps/web/src/components/forms/styles/index.ts

// ============================================================================
// IMPORTATION DES STYLES CSS
// ============================================================================

import './forms.css';

// ============================================================================
// EXPORTS DES CONSTANTES DE STYLES
// ============================================================================

/**
 * Classes CSS disponibles pour les formulaires
 */
export const FORM_STYLES = {
  // --- Containers ---
  container: 'form-container',
  containerSm: 'form-container-sm',
  containerMd: 'form-container-md',
  containerLg: 'form-container-lg',
  containerXl: 'form-container-xl',
  containerFull: 'form-container-full',
  
  // --- Formulaires ---
  form: 'form',
  formHorizontal: 'form-horizontal',
  formInline: 'form-inline',
  formGrid: 'form-grid',
  formGridCols2: 'form-grid-cols-2',
  formGridCols3: 'form-grid-cols-3',
  formGridCols4: 'form-grid-cols-4',
  
  // --- Groupes ---
  group: 'form-group',
  groupHorizontal: 'form-group-horizontal',
  groupInline: 'form-group-inline',
  
  // --- Labels ---
  label: 'form-label',
  labelRequired: 'form-label-required',
  labelDisabled: 'form-label-disabled',
  
  // --- Inputs ---
  input: 'form-input',
  inputXs: 'form-input-xs',
  inputSm: 'form-input-sm',
  inputMd: 'form-input-md',
  inputLg: 'form-input-lg',
  inputXl: 'form-input-xl',
  inputSuccess: 'form-input-success',
  inputError: 'form-input-error',
  inputWarning: 'form-input-warning',
  inputOutlined: 'form-input-outlined',
  inputSolid: 'form-input-solid',
  inputGhost: 'form-input-ghost',
  inputMinimal: 'form-input-minimal',
  inputPill: 'form-input-pill',
  inputDisabled: 'form-input-disabled',
  
  // --- Textarea ---
  textarea: 'form-textarea',
  textareaResizeNone: 'form-textarea-resize-none',
  textareaResizeHorizontal: 'form-textarea-resize-horizontal',
  textareaResizeVertical: 'form-textarea-resize-vertical',
  textareaResizeBoth: 'form-textarea-resize-both',
  textareaResizeAuto: 'form-textarea-resize-auto',
  
  // --- Select ---
  select: 'form-select',
  
  // --- Checkbox & Radio ---
  check: 'form-check',
  checkDisabled: 'form-check-disabled',
  checkInput: 'form-check-input',
  checkInputSm: 'form-check-input-sm',
  checkInputLg: 'form-check-input-lg',
  checkInputXl: 'form-check-input-xl',
  
  // --- Switch ---
  switch: 'form-switch',
  switchInput: 'form-switch-input',
  switchTrack: 'form-switch-track',
  switchThumb: 'form-switch-thumb',
  switchSm: 'form-switch-sm',
  switchLg: 'form-switch-lg',
  switchXl: 'form-switch-xl',
  
  // --- Messages ---
  message: 'form-message',
  messageError: 'form-message-error',
  messageSuccess: 'form-message-success',
  messageWarning: 'form-message-warning',
  messageInfo: 'form-message-info',
  messageIcon: 'form-message-icon',
  
  // --- Wizard ---
  wizard: 'form-wizard',
  wizardSteps: 'form-wizard-steps',
  wizardStep: 'form-wizard-step',
  wizardStepActive: 'form-wizard-step-active',
  wizardStepCompleted: 'form-wizard-step-completed',
  wizardStepNumber: 'form-wizard-step-number',
  wizardStepLine: 'form-wizard-step-line',
  
  // --- Card Layout ---
  card: 'form-card',
  cardHeader: 'form-card-header',
  cardTitle: 'form-card-title',
  cardSubtitle: 'form-card-subtitle',
  cardBody: 'form-card-body',
  cardFooter: 'form-card-footer',
  
  // --- Animations ---
  animateIn: 'form-animate-in',
  animateFade: 'form-animate-fade',
  animateScale: 'form-animate-scale',
  animateShake: 'form-animate-shake',
  
  // --- Helpers ---
  readOnly: 'form-readonly',
  inputWithIcon: 'form-input-with-icon',
  inputWithIconRight: 'form-input-with-icon-right',
  inputWithButton: 'form-input-with-button',
  noPrint: 'form-no-print',
  printOnly: 'form-print-only',
} as const;

// ============================================================================
// TYPES DES STYLES
// ============================================================================

export type FormStyleKey = keyof typeof FORM_STYLES;
export type FormStyleValue = typeof FORM_STYLES[FormStyleKey];

/**
 * Type pour une classe CSS de formulaire
 */
export type FormClassName = string;

/**
 * Type pour les props de style de formulaire
 */
export interface FormStyleProps {
  /** Classes additionnelles */
  className?: FormClassName;
  /** Styles inline */
  style?: React.CSSProperties;
}

// ============================================================================
// UTILITAIRES DE COMBINAISON DE CLASSES
// ============================================================================

/**
 * Combine plusieurs classes CSS en une seule chaîne
 */
export const combineFormClasses = (...classes: (string | undefined | null | false)[]): string => {
  return classes.filter(Boolean).join(' ');
};

/**
 * Combine des classes avec des conditions
 */
export const classNames = (
  ...args: (string | undefined | null | false | Record<string, boolean>)[]
): string => {
  const result: string[] = [];
  
  for (const arg of args) {
    if (!arg) continue;
    
    if (typeof arg === 'string') {
      result.push(arg);
    } else if (typeof arg === 'object') {
      for (const [key, value] of Object.entries(arg)) {
        if (value) result.push(key);
      }
    }
  }
  
  return result.join(' ');
};

// ============================================================================
// UTILITAIRES DE STYLE - VARIANTES
// ============================================================================

/**
 * Types de variantes pour les champs de formulaire
 */
export type FormInputVariant = 'default' | 'outlined' | 'solid' | 'ghost' | 'minimal' | 'pill';
export type FormInputSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type FormInputStatus = 'default' | 'success' | 'error' | 'warning' | 'info';
export type FormInputState = 'default' | 'hover' | 'focus' | 'disabled' | 'readonly';

/**
 * Mapping des classes CSS pour les variantes
 */
export const FORM_VARIANT_CLASSES = {
  input: {
    default: FORM_STYLES.input,
    outlined: FORM_STYLES.inputOutlined,
    solid: FORM_STYLES.inputSolid,
    ghost: FORM_STYLES.inputGhost,
    minimal: FORM_STYLES.inputMinimal,
    pill: FORM_STYLES.inputPill,
  },
  inputSize: {
    xs: FORM_STYLES.inputXs,
    sm: FORM_STYLES.inputSm,
    md: FORM_STYLES.inputMd,
    lg: FORM_STYLES.inputLg,
    xl: FORM_STYLES.inputXl,
  },
  inputStatus: {
    default: '',
    success: FORM_STYLES.inputSuccess,
    error: FORM_STYLES.inputError,
    warning: FORM_STYLES.inputWarning,
    info: '',
  },
  inputState: {
    default: '',
    hover: '',
    focus: '',
    disabled: FORM_STYLES.inputDisabled,
    readonly: FORM_STYLES.readOnly,
  },
  textarea: {
    default: FORM_STYLES.textarea,
    resizeNone: FORM_STYLES.textareaResizeNone,
    resizeHorizontal: FORM_STYLES.textareaResizeHorizontal,
    resizeVertical: FORM_STYLES.textareaResizeVertical,
    resizeBoth: FORM_STYLES.textareaResizeBoth,
    resizeAuto: FORM_STYLES.textareaResizeAuto,
  },
  check: {
    default: FORM_STYLES.check,
    disabled: FORM_STYLES.checkDisabled,
    input: FORM_STYLES.checkInput,
    inputSm: FORM_STYLES.checkInputSm,
    inputLg: FORM_STYLES.checkInputLg,
    inputXl: FORM_STYLES.checkInputXl,
  },
  switch: {
    default: FORM_STYLES.switch,
    input: FORM_STYLES.switchInput,
    track: FORM_STYLES.switchTrack,
    thumb: FORM_STYLES.switchThumb,
    sm: FORM_STYLES.switchSm,
    lg: FORM_STYLES.switchLg,
    xl: FORM_STYLES.switchXl,
  },
  message: {
    default: FORM_STYLES.message,
    error: FORM_STYLES.messageError,
    success: FORM_STYLES.messageSuccess,
    warning: FORM_STYLES.messageWarning,
    info: FORM_STYLES.messageInfo,
    icon: FORM_STYLES.messageIcon,
  },
  wizard: {
    default: FORM_STYLES.wizard,
    steps: FORM_STYLES.wizardSteps,
    step: FORM_STYLES.wizardStep,
    stepActive: FORM_STYLES.wizardStepActive,
    stepCompleted: FORM_STYLES.wizardStepCompleted,
    stepNumber: FORM_STYLES.wizardStepNumber,
    stepLine: FORM_STYLES.wizardStepLine,
  },
  card: {
    default: FORM_STYLES.card,
    header: FORM_STYLES.cardHeader,
    title: FORM_STYLES.cardTitle,
    subtitle: FORM_STYLES.cardSubtitle,
    body: FORM_STYLES.cardBody,
    footer: FORM_STYLES.cardFooter,
  },
  animation: {
    in: FORM_STYLES.animateIn,
    fade: FORM_STYLES.animateFade,
    scale: FORM_STYLES.animateScale,
    shake: FORM_STYLES.animateShake,
  },
} as const;

// ============================================================================
// FONCTIONS UTILITAIRES DE STYLE
// ============================================================================

/**
 * Obtient les classes CSS pour un input selon sa configuration
 */
export const getInputClasses = (
  variant: FormInputVariant = 'default',
  size: FormInputSize = 'md',
  status: FormInputStatus = 'default',
  state: FormInputState = 'default',
  additionalClasses?: string
): string => {
  const classes = [
    FORM_VARIANT_CLASSES.input[variant],
    FORM_VARIANT_CLASSES.inputSize[size],
    FORM_VARIANT_CLASSES.inputStatus[status],
    FORM_VARIANT_CLASSES.inputState[state],
    additionalClasses,
  ];
  return classNames(...classes);
};

/**
 * Obtient les classes CSS pour un textarea selon sa configuration
 */
export const getTextareaClasses = (
  resize: keyof typeof FORM_VARIANT_CLASSES.textarea = 'vertical',
  additionalClasses?: string
): string => {
  const classes = [
    FORM_VARIANT_CLASSES.textarea.default,
    FORM_VARIANT_CLASSES.textarea[resize],
    additionalClasses,
  ];
  return classNames(...classes);
};

/**
 * Obtient les classes CSS pour un switch selon sa configuration
 */
export const getSwitchClasses = (
  size: keyof typeof FORM_VARIANT_CLASSES.switch = 'default',
  additionalClasses?: string
): string => {
  const classes = [
    FORM_VARIANT_CLASSES.switch.default,
    size !== 'default' ? FORM_VARIANT_CLASSES.switch[size] : '',
    additionalClasses,
  ];
  return classNames(...classes);
};

/**
 * Obtient les classes CSS pour un message selon son type
 */
export const getMessageClasses = (
  type: keyof typeof FORM_VARIANT_CLASSES.message = 'default',
  additionalClasses?: string
): string => {
  const classes = [
    FORM_VARIANT_CLASSES.message.default,
    FORM_VARIANT_CLASSES.message[type],
    additionalClasses,
  ];
  return classNames(...classes);
};

/**
 * Obtient les classes CSS pour une carte selon sa configuration
 */
export const getCardClasses = (
  additionalClasses?: string
): string => {
  const classes = [
    FORM_VARIANT_CLASSES.card.default,
    additionalClasses,
  ];
  return classNames(...classes);
};

// ============================================================================
// CONSTANTES DE COULEURS
// ============================================================================

export const FORM_COLORS = {
  // Couleurs principales
  primary: 'var(--form-border-focus)',
  success: 'var(--form-border-success)',
  error: 'var(--form-border-error)',
  warning: 'var(--form-border-warning)',
  info: '#3b82f6',
  
  // Couleurs de fond
  background: 'var(--form-bg)',
  backgroundHover: 'var(--form-bg-hover)',
  backgroundFocus: 'var(--form-bg-focus)',
  backgroundDisabled: 'var(--form-bg-disabled)',
  
  // Couleurs de texte
  text: 'var(--form-text)',
  textSecondary: 'var(--form-text-secondary)',
  textPlaceholder: 'var(--form-text-placeholder)',
  textDisabled: 'var(--form-text-disabled)',
  
  // Couleurs de bordure
  border: 'var(--form-border)',
  borderHover: 'var(--form-border-hover)',
  borderFocus: 'var(--form-border-focus)',
  borderError: 'var(--form-border-error)',
  borderSuccess: 'var(--form-border-success)',
  borderWarning: 'var(--form-border-warning)',
  
  // Couleurs de ring
  ringFocus: 'var(--form-ring-focus)',
  ringError: 'var(--form-ring-error)',
  ringSuccess: 'var(--form-ring-success)',
  ringWarning: 'var(--form-ring-warning)',
} as const;

// ============================================================================
// CONSTANTES DE TAILLES
// ============================================================================

export const FORM_SIZES = {
  input: {
    xs: 'var(--form-input-height-xs)',
    sm: 'var(--form-input-height-sm)',
    md: 'var(--form-input-height-md)',
    lg: 'var(--form-input-height-lg)',
    xl: 'var(--form-input-height-xl)',
  },
  spacing: {
    xs: 'var(--form-spacing-xs)',
    sm: 'var(--form-spacing-sm)',
    md: 'var(--form-spacing-md)',
    lg: 'var(--form-spacing-lg)',
    xl: 'var(--form-spacing-xl)',
  },
  borderRadius: {
    sm: 'var(--form-border-radius-sm)',
    md: 'var(--form-border-radius-md)',
    lg: 'var(--form-border-radius-lg)',
    xl: 'var(--form-border-radius-xl)',
    '2xl': 'var(--form-border-radius-2xl)',
  },
  shadow: {
    sm: 'var(--form-shadow-sm)',
    md: 'var(--form-shadow-md)',
    lg: 'var(--form-shadow-lg)',
    xl: 'var(--form-shadow-xl)',
  },
} as const;

// ============================================================================
// EXPORTATION DES STYLES PAR DÉFAUT
// ============================================================================

/**
 * Exportation groupée de tous les styles de formulaire
 */
const FormStyles = {
  // Constantes
  STYLES: FORM_STYLES,
  COLORS: FORM_COLORS,
  SIZES: FORM_SIZES,
  VARIANT_CLASSES: FORM_VARIANT_CLASSES,
  
  // Utilitaires
  combineClasses: combineFormClasses,
  classNames,
  getInputClasses,
  getTextareaClasses,
  getSwitchClasses,
  getMessageClasses,
  getCardClasses,
};

export default FormStyles;

// ============================================================================
// EXPORTATION DES TYPES
// ============================================================================

export type {
  FormStyleKey,
  FormStyleValue,
  FormClassName,
  FormStyleProps,
  FormInputVariant,
  FormInputSize,
  FormInputStatus,
  FormInputState,
} from './types';

// ============================================================================
// EXPORTATION DES VALIDATEURS DE STYLE
// ============================================================================

export const isValidStyleKey = (key: string): key is FormStyleKey => {
  return key in FORM_STYLES;
};

export const isValidInputVariant = (variant: string): variant is FormInputVariant => {
  return ['default', 'outlined', 'solid', 'ghost', 'minimal', 'pill'].includes(variant);
};

export const isValidInputSize = (size: string): size is FormInputSize => {
  return ['xs', 'sm', 'md', 'lg', 'xl'].includes(size);
};

export const isValidInputStatus = (status: string): status is FormInputStatus => {
  return ['default', 'success', 'error', 'warning', 'info'].includes(status);
};

export const isValidInputState = (state: string): state is FormInputState => {
  return ['default', 'hover', 'focus', 'disabled', 'readonly'].includes(state);
};

// ============================================================================
// UTILITAIRES DE THÈME
// ============================================================================

export const isDarkMode = (): boolean => {
  if (typeof window === 'undefined') return false;
  return document.documentElement.classList.contains('dark');
};

export const getThemeColor = (colorName: keyof typeof FORM_COLORS): string => {
  return FORM_COLORS[colorName] || FORM_COLORS.primary;
};

export const getThemeVariable = (variableName: string): string => {
  if (typeof window === 'undefined') return '';
  return getComputedStyle(document.documentElement)
    .getPropertyValue(variableName)
    .trim();
};

// ============================================================================
// EXPORTATION DES STYLES CSS
// ============================================================================

export * from './forms.css';

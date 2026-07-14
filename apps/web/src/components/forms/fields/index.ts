// apps/web/src/components/forms/fields/index.ts

// ============================================================================
// EXPORTS PRINCIPAUX - CHAMPS DE FORMULAIRE
// ============================================================================

// --- Champs de base ---
export { default as TextField } from './TextField';
export type {
  TextFieldProps,
  TextFieldVariant,
  TextFieldSize,
  TextFieldStatus,
  TextFieldInputMode,
  TextFieldAutocomplete,
} from './TextField';

export { default as TextareaField } from './TextareaField';
export type {
  TextareaFieldProps,
  TextareaVariant,
  TextareaSize,
  TextareaStatus,
  TextareaResize,
} from './TextareaField';

export { default as NumberField } from './NumberField';
export type {
  NumberFieldProps,
  NumberFormat,
  NumberRounding,
  NumberDisplay,
  NumberFieldVariant,
  NumberStepper,
} from './NumberField';

// --- Champs spécialisés ---
export { default as EmailField } from './EmailField';
export type {
  EmailFieldProps,
  EmailValidationLevel,
  EmailSuggestion,
} from './EmailField';

export { default as PasswordField } from './PasswordField';
export type {
  PasswordFieldProps,
  PasswordStrength,
  PasswordValidationLevel,
  PasswordFieldVariant,
  PasswordVisibility,
} from './PasswordField';

export { default as PhoneField } from './PhoneField';
export type {
  PhoneFieldProps,
  PhoneCountry,
  PhoneFieldVariant,
  PhoneFormat,
  PhoneValidationLevel,
} from './PhoneField';
export { COUNTRIES } from './PhoneField';

export { default as UrlField } from './UrlField';
export type {
  UrlFieldProps,
  UrlProtocol,
  UrlValidationLevel,
  UrlStatus,
  UrlPreview,
} from './UrlField';

// --- Champs de sélection ---
export { default as SelectField } from './SelectField';
export type {
  SelectFieldProps,
  SelectOption,
  SelectGroup,
  SelectVariant,
  SelectSize,
  SelectColor,
  SelectStatus,
  SelectPlacement,
} from './SelectField';

export { default as RadioGroupField } from './RadioGroupField';
export type {
  RadioGroupFieldProps,
  RadioOption,
  RadioVariant,
  RadioSize,
  RadioColor,
  RadioDirection,
  RadioAlignment,
} from './RadioGroupField';

// --- Champs de date/heure ---
export { default as DateField } from './DateField';
export type {
  DateFieldProps,
  DateFormat,
  DateDisplay,
  DateRange,
  DatePickerVariant,
} from './DateField';

export { default as TimeField } from './TimeField';
export type {
  TimeFieldProps,
  TimeFormat,
  TimeVariant,
  TimeSize,
  TimeStatus,
  TimeStep,
} from './TimeField';

export { default as DateTimeField } from './DateTimeField';
export type {
  DateTimeFieldProps,
  DateTimeFormat,
  TimeFormat as DateTimeTimeFormat,
  Timezone,
  DateTimePickerVariant,
} from './DateTimeField';

// --- Champs de plage ---
export { default as RangeField } from './RangeField';
export type {
  RangeFieldProps,
  RangeValue,
  RangeVariant,
  RangeDisplay,
  RangeMark,
} from './RangeField';

export { default as SliderField } from './SliderField';
export type {
  SliderFieldProps,
  SliderDisplay,
  SliderVariant,
  SliderMark,
} from './SliderField';

export { default as PercentageField } from './PercentageField';
export type {
  PercentageFieldProps,
  PercentageDisplay,
  PercentageRounding,
  PercentageFieldVariant,
  PercentageMode,
} from './PercentageField';

// --- Champs de fichiers ---
export { default as FileField } from './FileField';
export type {
  FileFieldProps,
  UploadFile,
  FileStatus,
  FileType,
  FileUploadVariant,
} from './FileField';

export { default as ImageField } from './ImageField';
export type {
  ImageFieldProps,
  UploadImage,
  ImageStatus,
  ImageFit,
  ImagePosition,
} from './ImageField';

// --- Champs de devises ---
export { default as CurrencyField } from './CurrencyField';
export type {
  CurrencyFieldProps,
  CurrencyCode,
  CurrencyInfo,
  CurrencyDisplay,
  CurrencyFormat,
  CurrencyRounding,
} from './CurrencyField';
export { CURRENCIES, DEFAULT_CURRENCY } from './CurrencyField';

// --- Champs de toggles ---
export { default as SwitchField } from './SwitchField';
export type {
  SwitchFieldProps,
  SwitchVariant,
  SwitchSize,
  SwitchLabelPosition,
  SwitchAnimation,
} from './SwitchField';

export { default as ToggleField } from './ToggleField';
export type {
  ToggleFieldProps,
  ToggleVariant,
  ToggleSize,
  ToggleLabelPosition,
  ToggleAnimation,
  ToggleVariantStyle,
} from './ToggleField';

// --- Champs de tags ---
export { default as TagsField } from './TagsField';
export type {
  TagsFieldProps,
  Tag,
  TagVariant,
  TagSize,
  TagColor,
  TagSource,
} from './TagsField';

// --- Champs de texte enrichi ---
export { default as RichTextField } from './RichTextField';
export type {
  RichTextFieldProps,
  RichTextFormat,
  RichTextVariant,
  RichTextToolbar,
  RichTextMode,
  RichTextToolbarConfig,
} from './RichTextField';

// ============================================================================
// EXPORTS DE TYPE - TYPES GÉNÉRIQUES
// ============================================================================

export type FieldVariant = 
  | TextFieldVariant
  | TextareaVariant
  | NumberFieldVariant
  | PasswordFieldVariant
  | PhoneFieldVariant
  | SelectVariant
  | RadioVariant
  | DatePickerVariant
  | TimeVariant
  | DateTimePickerVariant
  | RangeVariant
  | SliderVariant
  | PercentageFieldVariant
  | FileUploadVariant
  | RichTextVariant
  | TagVariant
  | SwitchVariant
  | ToggleVariant;

export type FieldSize = 
  | TextFieldSize
  | TextareaSize
  | NumberFieldSize
  | PasswordFieldSize
  | PhoneFieldSize
  | SelectSize
  | RadioSize
  | SwitchSize
  | ToggleSize
  | TagSize;

export type FieldStatus = 
  | TextFieldStatus
  | TextareaStatus
  | SelectStatus
  | TimeStatus
  | FileStatus
  | ImageStatus
  | RichTextStatus;

export type FieldColor = 
  | SelectColor
  | RadioColor
  | TagColor;

// ============================================================================
// CONSTANTES - CONFIGURATIONS PAR DÉFAUT
// ============================================================================

export const DEFAULT_FIELD_CONFIG = {
  // Taille par défaut
  size: 'md' as FieldSize,
  
  // Variante par défaut
  variant: 'default' as FieldVariant,
  
  // Statut par défaut
  status: 'default' as FieldStatus,
  
  // Couleur par défaut
  color: 'brand' as FieldColor,
  
  // Validation
  required: false,
  disabled: false,
  
  // Formatage
  showValidationIcon: true,
  showCharCount: true,
  
  // Accessibilité
  autoComplete: 'on',
} as const;

// ============================================================================
// UTILITAIRES - VALIDATION
// ============================================================================

export const validateField = <T = any>(
  value: T,
  rules?: {
    required?: boolean;
    minLength?: number;
    maxLength?: number;
    min?: number;
    max?: number;
    pattern?: RegExp;
    custom?: (value: T) => boolean | string;
  }
): { valid: boolean; message: string } => {
  if (!rules) return { valid: true, message: '' };

  // Required
  if (rules.required) {
    if (value === undefined || value === null || value === '') {
      return { valid: false, message: 'Ce champ est requis' };
    }
    if (Array.isArray(value) && value.length === 0) {
      return { valid: false, message: 'Ce champ est requis' };
    }
  }

  // MinLength / MaxLength (pour les strings)
  if (typeof value === 'string') {
    if (rules.minLength && value.length < rules.minLength) {
      return { valid: false, message: `Minimum ${rules.minLength} caractères` };
    }
    if (rules.maxLength && value.length > rules.maxLength) {
      return { valid: false, message: `Maximum ${rules.maxLength} caractères` };
    }
    if (rules.pattern && !rules.pattern.test(value)) {
      return { valid: false, message: 'Format invalide' };
    }
  }

  // Min / Max (pour les nombres)
  if (typeof value === 'number') {
    if (rules.min !== undefined && value < rules.min) {
      return { valid: false, message: `Valeur minimale: ${rules.min}` };
    }
    if (rules.max !== undefined && value > rules.max) {
      return { valid: false, message: `Valeur maximale: ${rules.max}` };
    }
  }

  // Custom validation
  if (rules.custom) {
    const result = rules.custom(value);
    if (typeof result === 'string') {
      return { valid: false, message: result };
    }
    if (result === false) {
      return { valid: false, message: 'Valeur invalide' };
    }
  }

  return { valid: true, message: '' };
};

// ============================================================================
// UTILITAIRES - FORMATAGE
// ============================================================================

export const formatFieldValue = (
  value: any,
  format?: 'text' | 'number' | 'currency' | 'percentage' | 'phone' | 'email' | 'url'
): string => {
  if (value === undefined || value === null) return '';

  switch (format) {
    case 'number':
      return new Intl.NumberFormat('fr-FR').format(value);
    case 'currency':
      return new Intl.NumberFormat('fr-FR', {
        style: 'currency',
        currency: 'EUR',
      }).format(value);
    case 'percentage':
      return new Intl.NumberFormat('fr-FR', {
        style: 'percent',
        minimumFractionDigits: 1,
      }).format(value);
    case 'phone':
      return String(value);
    case 'email':
      return String(value).toLowerCase();
    case 'url':
      return String(value);
    default:
      return String(value);
  }
};

// ============================================================================
// HOOKS
// ============================================================================

export { useField } from '@/hooks/useField';
export { useFieldValidation } from '@/hooks/useFieldValidation';

// ============================================================================
// EXPORTATION PAR DÉFAUT - TOUS LES CHAMPS
// ============================================================================

/**
 * Exportation groupée de tous les champs de formulaire
 */
const FormFields = {
  Text: TextField,
  Textarea: TextareaField,
  Number: NumberField,
  Email: EmailField,
  Password: PasswordField,
  Phone: PhoneField,
  Url: UrlField,
  Select: SelectField,
  RadioGroup: RadioGroupField,
  Date: DateField,
  Time: TimeField,
  DateTime: DateTimeField,
  Range: RangeField,
  Slider: SliderField,
  Percentage: PercentageField,
  File: FileField,
  Image: ImageField,
  Currency: CurrencyField,
  Switch: SwitchField,
  Toggle: ToggleField,
  Tags: TagsField,
  RichText: RichTextField,
};

export default FormFields;

// ============================================================================
// TYPES DÉRIVÉS POUR UNE UTILISATION FACILE
// ============================================================================

/**
 * Type union de tous les noms de champs
 */
export type FieldName = 
  | 'Text'
  | 'Textarea'
  | 'Number'
  | 'Email'
  | 'Password'
  | 'Phone'
  | 'Url'
  | 'Select'
  | 'RadioGroup'
  | 'Date'
  | 'Time'
  | 'DateTime'
  | 'Range'
  | 'Slider'
  | 'Percentage'
  | 'File'
  | 'Image'
  | 'Currency'
  | 'Switch'
  | 'Toggle'
  | 'Tags'
  | 'RichText';

/**
 * Mapping des props pour chaque champ
 */
export interface FieldPropsMap {
  Text: TextFieldProps;
  Textarea: TextareaFieldProps;
  Number: NumberFieldProps;
  Email: EmailFieldProps;
  Password: PasswordFieldProps;
  Phone: PhoneFieldProps;
  Url: UrlFieldProps;
  Select: SelectFieldProps;
  RadioGroup: RadioGroupFieldProps;
  Date: DateFieldProps;
  Time: TimeFieldProps;
  DateTime: DateTimeFieldProps;
  Range: RangeFieldProps;
  Slider: SliderFieldProps;
  Percentage: PercentageFieldProps;
  File: FileFieldProps;
  Image: ImageFieldProps;
  Currency: CurrencyFieldProps;
  Switch: SwitchFieldProps;
  Toggle: ToggleFieldProps;
  Tags: TagsFieldProps;
  RichText: RichTextFieldProps;
}

/**
 * Type générique pour obtenir les props d'un champ spécifique
 */
export type FieldProps<T extends FieldName> = FieldPropsMap[T];

/**
 * Type générique pour les données d'un champ spécifique
 */
export type FieldDataMap = {
  Text: string | null;
  Textarea: string | null;
  Number: number | null;
  Email: string | null;
  Password: string | null;
  Phone: string | null;
  Url: string | null;
  Select: string | string[] | null;
  RadioGroup: string | null;
  Date: Date | string | null;
  Time: string | null;
  DateTime: Date | string | null;
  Range: [number, number] | null;
  Slider: number | [number, number] | null;
  Percentage: number | null;
  File: UploadFile[] | null;
  Image: UploadImage[] | UploadImage | null;
  Currency: number | string | null;
  Switch: boolean;
  Toggle: boolean;
  Tags: Tag[] | null;
  RichText: string | null;
};

export type FieldData<T extends FieldName> = FieldDataMap[T];

// ============================================================================
// CONFIGURATION DES CHAMPS
// ============================================================================

export const FIELD_CONFIGS = {
  Text: {
    label: 'Texte',
    icon: '📝',
    defaultPlaceholder: 'Saisissez du texte...',
  },
  Textarea: {
    label: 'Zone de texte',
    icon: '📄',
    defaultPlaceholder: 'Saisissez du texte long...',
  },
  Number: {
    label: 'Nombre',
    icon: '🔢',
    defaultPlaceholder: '0',
  },
  Email: {
    label: 'Email',
    icon: '📧',
    defaultPlaceholder: 'exemple@email.com',
  },
  Password: {
    label: 'Mot de passe',
    icon: '🔒',
    defaultPlaceholder: '••••••••',
  },
  Phone: {
    label: 'Téléphone',
    icon: '📱',
    defaultPlaceholder: '06 12 34 56 78',
  },
  Url: {
    label: 'URL',
    icon: '🔗',
    defaultPlaceholder: 'https://exemple.com',
  },
  Select: {
    label: 'Sélection',
    icon: '📋',
    defaultPlaceholder: 'Sélectionner...',
  },
  RadioGroup: {
    label: 'Choix',
    icon: '⭕',
    defaultPlaceholder: 'Sélectionner une option',
  },
  Date: {
    label: 'Date',
    icon: '📅',
    defaultPlaceholder: 'dd/mm/yyyy',
  },
  Time: {
    label: 'Heure',
    icon: '🕐',
    defaultPlaceholder: 'HH:mm',
  },
  DateTime: {
    label: 'Date et heure',
    icon: '📅🕐',
    defaultPlaceholder: 'dd/mm/yyyy HH:mm',
  },
  Range: {
    label: 'Plage',
    icon: '📊',
    defaultPlaceholder: 'Min - Max',
  },
  Slider: {
    label: 'Slider',
    icon: '🎚️',
    defaultPlaceholder: '',
  },
  Percentage: {
    label: 'Pourcentage',
    icon: '💯',
    defaultPlaceholder: '0%',
  },
  File: {
    label: 'Fichier',
    icon: '📎',
    defaultPlaceholder: 'Déposez vos fichiers ici',
  },
  Image: {
    label: 'Image',
    icon: '🖼️',
    defaultPlaceholder: 'Déposez vos images ici',
  },
  Currency: {
    label: 'Devise',
    icon: '💰',
    defaultPlaceholder: '0.00',
  },
  Switch: {
    label: 'Interrupteur',
    icon: '🔘',
    defaultPlaceholder: '',
  },
  Toggle: {
    label: 'Bascule',
    icon: '🔄',
    defaultPlaceholder: '',
  },
  Tags: {
    label: 'Tags',
    icon: '🏷️',
    defaultPlaceholder: 'Ajouter un tag...',
  },
  RichText: {
    label: 'Texte enrichi',
    icon: '📝',
    defaultPlaceholder: 'Saisissez votre texte enrichi...',
  },
} as const;

// ============================================================================
// EXPORTATION DES VALIDATEURS
// ============================================================================

export * from '../validators/fieldValidators';

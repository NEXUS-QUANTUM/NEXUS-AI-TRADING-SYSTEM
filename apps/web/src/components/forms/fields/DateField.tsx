// apps/web/src/components/forms/fields/DateField.tsx
'use client';

import React, {
  useState,
  useCallback,
  useRef,
  useEffect,
  forwardRef,
  Ref,
  useMemo,
  useImperativeHandle,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CalendarIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  XMarkIcon,
  CheckIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ClockIcon,
  PlusIcon,
  MinusIcon,
  CalendarDaysIcon,
  ListBulletIcon,
  Squares2X2Icon,
  ArrowLeftIcon,
  ArrowRightIcon,
  TodayIcon,
  MoonIcon,
  SunIcon,
} from '@heroicons/react/24/outline';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';
import { Popover } from '@/components/common/Popover';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type DateFormat = 'dd/MM/yyyy' | 'MM/dd/yyyy' | 'yyyy-MM-dd' | 'dd-MM-yyyy' | 'MM-dd-yyyy' | 'yyyy/MM/dd' | 'dd.MM.yyyy' | 'MM.dd.yyyy';
export type DateDisplay = 'calendar' | 'list' | 'grid';
export type DateRange = 'day' | 'week' | 'month' | 'quarter' | 'year' | 'custom';
export type DatePickerVariant = 'default' | 'compact' | 'minimal' | 'rounded' | 'outlined';

export interface DateFieldProps {
  // --- Contrôle ---
  /** Valeur du champ (Date ou string) */
  value?: Date | string | null;
  /** Valeur par défaut */
  defaultValue?: Date | string | null;
  /** Callback de changement */
  onChange?: (value: Date | null) => void;
  /** Callback de blur */
  onBlur?: () => void;
  /** Callback de focus */
  onFocus?: () => void;
  /** Callback de validation */
  onValidate?: (valid: boolean, value: Date | null) => void;

  // --- Apparence ---
  /** Libellé du champ */
  label?: string;
  /** Placeholder */
  placeholder?: string;
  /** Description */
  description?: string;
  /** Message d'erreur */
  error?: string;
  /** Message de succès */
  success?: string;
  /** Message d'information */
  info?: string;
  /** Format d'affichage */
  dateFormat?: DateFormat;
  /** Variante du picker */
  variant?: DatePickerVariant;
  /** Afficher le sélecteur de date */
  showPicker?: boolean;
  /** Afficher les raccourcis */
  showShortcuts?: boolean;
  /** Afficher le temps */
  showTime?: boolean;
  /** Afficher le bouton "Aujourd'hui" */
  showTodayButton?: boolean;
  /** Afficher le bouton "Effacer" */
  showClearButton?: boolean;
  /** Afficher le sélecteur de mois/année */
  showMonthYearSelector?: boolean;
  /** Mode d'affichage par défaut */
  defaultDisplay?: DateDisplay;

  // --- Comportement ---
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Désactiver les dates passées */
  disablePast?: boolean;
  /** Désactiver les dates futures */
  disableFuture?: boolean;
  /** Date minimale */
  minDate?: Date | string;
  /** Date maximale */
  maxDate?: Date | string;
  /** Jours désactivés (0=Dim, 6=Sam) */
  disabledDays?: number[];
  /** Dates désactivées */
  disabledDates?: Date[];
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;

  // --- Raccourcis ---
  /** Raccourcis de dates */
  shortcuts?: { label: string; value: DateRange | Date }[];
  /** Raccourcis par défaut */
  defaultShortcuts?: DateRange[];

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ARIA describedby */
  ariaDescribedby?: string;
  /** ID */
  id?: string;
  /** Nom du champ */
  name?: string;

  // --- Avancé ---
  /** Fonction de formatage personnalisée */
  customFormat?: (date: Date) => string;
  /** Fonction de parsing personnalisée */
  customParse?: (value: string) => Date | null;
  /** Fonction de validation personnalisée */
  customValidate?: (date: Date | null) => boolean | string;
  /** Fonction pour désactiver une date */
  isDateDisabled?: (date: Date) => boolean;
  /** Ref */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const DATE_FORMATS: Record<DateFormat, { format: string; separator: string; order: ('d' | 'm' | 'y')[] }> = {
  'dd/MM/yyyy': { format: 'dd/MM/yyyy', separator: '/', order: ['d', 'm', 'y'] },
  'MM/dd/yyyy': { format: 'MM/dd/yyyy', separator: '/', order: ['m', 'd', 'y'] },
  'yyyy-MM-dd': { format: 'yyyy-MM-dd', separator: '-', order: ['y', 'm', 'd'] },
  'dd-MM-yyyy': { format: 'dd-MM-yyyy', separator: '-', order: ['d', 'm', 'y'] },
  'MM-dd-yyyy': { format: 'MM-dd-yyyy', separator: '-', order: ['m', 'd', 'y'] },
  'yyyy/MM/dd': { format: 'yyyy/MM/dd', separator: '/', order: ['y', 'm', 'd'] },
  'dd.MM.yyyy': { format: 'dd.MM.yyyy', separator: '.', order: ['d', 'm', 'y'] },
  'MM.dd.yyyy': { format: 'MM.dd.yyyy', separator: '.', order: ['m', 'd', 'y'] },
};

const DAYS_OF_WEEK = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'];
const MONTHS = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];

const DEFAULT_SHORTCUTS: { label: string; value: DateRange }[] = [
  { label: "Aujourd'hui", value: 'day' },
  { label: 'Cette semaine', value: 'week' },
  { label: 'Ce mois', value: 'month' },
  { label: 'Ce trimestre', value: 'quarter' },
  { label: 'Cette année', value: 'year' },
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const DateField = forwardRef<HTMLInputElement, DateFieldProps>(
  (props, ref) => {
    const {
      // Contrôle
      value: externalValue,
      defaultValue,
      onChange,
      onBlur,
      onFocus,
      onValidate,

      // Apparence
      label,
      placeholder = 'Sélectionner une date',
      description,
      error,
      success,
      info,
      dateFormat = 'dd/MM/yyyy',
      variant = 'default',
      showPicker = true,
      showShortcuts = true,
      showTime = false,
      showTodayButton = true,
      showClearButton = true,
      showMonthYearSelector = true,
      defaultDisplay = 'calendar',

      // Comportement
      disabled = false,
      required = false,
      disablePast = false,
      disableFuture = false,
      minDate,
      maxDate,
      disabledDays = [],
      disabledDates = [],
      disableRealtimeValidation = false,

      // Raccourcis
      shortcuts,
      defaultShortcuts = ['day', 'week', 'month'],

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,
      name,

      // Avancé
      customFormat,
      customParse,
      customValidate,
      isDateDisabled,
      inputRef,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const inputRefInternal = useRef<HTMLInputElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const calendarRef = useRef<HTMLDivElement>(null);
    const prevValueRef = useRef<Date | null>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState<Date | null>(
      defaultValue ? new Date(defaultValue) : null
    );
    const [displayValue, setDisplayValue] = useState<string>('');
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');
    const [currentMonth, setCurrentMonth] = useState<Date>(new Date());
    const [selectedDate, setSelectedDate] = useState<Date | null>(
      defaultValue ? new Date(defaultValue) : null
    );
    const [isPickerOpen, setIsPickerOpen] = useState(false);
    const [displayMode, setDisplayMode] = useState<DateDisplay>(defaultDisplay);
    const [viewMode, setViewMode] = useState<'days' | 'months' | 'years'>('days');
    const [tempDate, setTempDate] = useState<Date | null>(null);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? (externalValue ? new Date(externalValue) : null) : internalValue;
    const isControlled = externalValue !== undefined;
    const formatInfo = DATE_FORMATS[dateFormat] || DATE_FORMATS['dd/MM/yyyy'];
    const minDateObj = minDate ? new Date(minDate) : null;
    const maxDateObj = maxDate ? new Date(maxDate) : null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // ========================================================================
    // FORMATAGE
    // ========================================================================

    const formatDate = useCallback((date: Date | null): string => {
      if (!date) return '';

      if (customFormat) {
        return customFormat(date);
      }

      const d = date.getDate().toString().padStart(2, '0');
      const m = (date.getMonth() + 1).toString().padStart(2, '0');
      const y = date.getFullYear().toString();

      const parts: Record<'d' | 'm' | 'y', string> = { d, m, y };
      const orderedParts = formatInfo.order.map(key => parts[key]);

      return orderedParts.join(formatInfo.separator);
    }, [dateFormat, customFormat, formatInfo]);

    const parseDate = useCallback((text: string): Date | null => {
      if (!text || text.trim() === '') return null;

      if (customParse) {
        return customParse(text);
      }

      const cleaned = text.replace(/\s/g, '');
      const parts = cleaned.split(new RegExp(`[${formatInfo.separator}/.]`));
      
      if (parts.length !== 3) return null;

      const values: Record<'d' | 'm' | 'y', number> = { d: 0, m: 0, y: 0 };
      const order = formatInfo.order;

      for (let i = 0; i < 3; i++) {
        const key = order[i];
        const val = parseInt(parts[i]);
        if (isNaN(val)) return null;
        values[key] = val;
      }

      // Ajuster l'année si 2 chiffres
      let year = values.y;
      if (year < 100) {
        year += year >= 50 ? 1900 : 2000;
      }

      const date = new Date(year, values.m - 1, values.d);
      if (isNaN(date.getTime())) return null;

      return date;
    }, [dateFormat, customParse, formatInfo]);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateDate = useCallback((date: Date | null): { valid: boolean; message: string } => {
      if (customValidate) {
        const result = customValidate(date);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (!date) {
        if (required) {
          return { valid: false, message: 'Ce champ est requis' };
        }
        return { valid: true, message: '' };
      }

      const d = new Date(date);
      d.setHours(0, 0, 0, 0);

      // Vérifier la date invalide
      if (isNaN(d.getTime())) {
        return { valid: false, message: 'Date invalide' };
      }

      // Vérifier les dates passées
      if (disablePast && d < today) {
        return { valid: false, message: 'Les dates passées ne sont pas autorisées' };
      }

      // Vérifier les dates futures
      if (disableFuture && d > today) {
        return { valid: false, message: 'Les dates futures ne sont pas autorisées' };
      }

      // Vérifier la date minimale
      if (minDateObj && d < minDateObj) {
        return { valid: false, message: `La date minimale est ${formatDate(minDateObj)}` };
      }

      // Vérifier la date maximale
      if (maxDateObj && d > maxDateObj) {
        return { valid: false, message: `La date maximale est ${formatDate(maxDateObj)}` };
      }

      // Vérifier les jours désactivés
      if (disabledDays.includes(d.getDay())) {
        return { valid: false, message: 'Ce jour n\'est pas autorisé' };
      }

      // Vérifier les dates désactivées
      if (disabledDates.some(dd => dd.toDateString() === d.toDateString())) {
        return { valid: false, message: 'Cette date n\'est pas autorisée' };
      }

      return { valid: true, message: '' };
    }, [
      required,
      disablePast,
      disableFuture,
      minDateObj,
      maxDateObj,
      disabledDays,
      disabledDates,
      formatDate,
      today,
      customValidate,
    ]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((date: Date | null) => {
      const validation = validateDate(date);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, date);
      }

      if (isControlled) {
        if (onChange) onChange(date);
      } else {
        setInternalValue(date);
        if (onChange) onChange(date);
      }

      const formatted = formatDate(date);
      setDisplayValue(formatted);
      setSelectedDate(date);

      if (debug) {
        console.log('DateField update:', { date, formatted, isValid: validation.valid });
      }
    }, [
      formatDate,
      validateDate,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      const rawValue = e.target.value;
      setDisplayValue(rawValue);

      if (!disableRealtimeValidation) {
        const parsed = parseDate(rawValue);
        const validation = validateDate(parsed);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        if (onValidate) onValidate(validation.valid, parsed);
      }
    }, [disableRealtimeValidation, parseDate, validateDate, onValidate]);

    const handleFocus = useCallback((e: React.FocusEvent<HTMLInputElement>) => {
      setIsFocused(true);
      if (onFocus) onFocus();
    }, [onFocus]);

    const handleBlur = useCallback((e: React.FocusEvent<HTMLInputElement>) => {
      setIsFocused(false);

      const parsed = parseDate(e.target.value);
      const validation = validateDate(parsed);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);
      if (onValidate) onValidate(validation.valid, parsed);

      if (parsed) {
        updateValue(parsed);
      } else if (!e.target.value) {
        updateValue(null);
      } else {
        setDisplayValue(formatDate(value));
      }

      if (onBlur) onBlur();
    }, [parseDate, validateDate, onValidate, updateValue, formatDate, value, onBlur]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const parsed = parseDate(displayValue);
        if (parsed) {
          updateValue(parsed);
        }
        inputRefInternal.current?.blur();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setDisplayValue(formatDate(value));
        inputRefInternal.current?.blur();
      }
    }, [displayValue, parseDate, updateValue, formatDate, value]);

    // ========================================================================
    // CALENDRIER
    // ========================================================================

    const getDaysInMonth = useCallback((date: Date) => {
      const year = date.getFullYear();
      const month = date.getMonth();
      const firstDay = new Date(year, month, 1);
      const lastDay = new Date(year, month + 1, 0);
      const daysInMonth = lastDay.getDate();
      const startDayOfWeek = firstDay.getDay();
      
      const days = [];
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      // Jours du mois précédent
      const prevMonthLastDay = new Date(year, month, 0).getDate();
      for (let i = startDayOfWeek - 1; i >= 0; i--) {
        const day = prevMonthLastDay - i;
        const date = new Date(year, month - 1, day);
        days.push({ date, day, isCurrentMonth: false, isToday: false });
      }

      // Jours du mois courant
      for (let i = 1; i <= daysInMonth; i++) {
        const date = new Date(year, month, i);
        const isToday = date.toDateString() === today.toDateString();
        days.push({ date, day: i, isCurrentMonth: true, isToday });
      }

      // Jours du mois suivant
      const remainingDays = 42 - days.length;
      for (let i = 1; i <= remainingDays; i++) {
        const date = new Date(year, month + 1, i);
        days.push({ date, day: i, isCurrentMonth: false, isToday: false });
      }

      return days;
    }, []);

    const isDateDisabledCheck = useCallback((date: Date) => {
      const d = new Date(date);
      d.setHours(0, 0, 0, 0);

      if (isDateDisabled) return isDateDisabled(d);
      
      if (disablePast && d < today) return true;
      if (disableFuture && d > today) return true;
      if (minDateObj && d < minDateObj) return true;
      if (maxDateObj && d > maxDateObj) return true;
      if (disabledDays.includes(d.getDay())) return true;
      if (disabledDates.some(dd => dd.toDateString() === d.toDateString())) return true;
      
      return false;
    }, [isDateDisabled, disablePast, disableFuture, minDateObj, maxDateObj, disabledDays, disabledDates, today]);

    const handleDateSelect = useCallback((date: Date) => {
      if (isDateDisabledCheck(date)) return;
      
      const selected = new Date(date);
      if (showTime) {
        // Conserver l'heure actuelle si le temps est affiché
        const currentTime = value || new Date();
        selected.setHours(currentTime.getHours(), currentTime.getMinutes(), 0, 0);
      }
      
      updateValue(selected);
      setIsPickerOpen(false);
    }, [isDateDisabledCheck, showTime, value, updateValue]);

    const handleMonthChange = useCallback((delta: number) => {
      const newDate = new Date(currentMonth);
      newDate.setMonth(newDate.getMonth() + delta);
      setCurrentMonth(newDate);
    }, [currentMonth]);

    const handleYearChange = useCallback((delta: number) => {
      const newDate = new Date(currentMonth);
      newDate.setFullYear(newDate.getFullYear() + delta);
      setCurrentMonth(newDate);
    }, [currentMonth]);

    const handleToday = useCallback(() => {
      const today = new Date();
      updateValue(today);
      setCurrentMonth(today);
      setIsPickerOpen(false);
    }, [updateValue]);

    const handleClear = useCallback(() => {
      updateValue(null);
      setDisplayValue('');
      setIsPickerOpen(false);
    }, [updateValue]);

    // ========================================================================
    // RACCOURCIS
    // ========================================================================

    const getShortcutDate = useCallback((range: DateRange): Date | null => {
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

      switch (range) {
        case 'day':
          return today;
        case 'week': {
          const weekStart = new Date(today);
          weekStart.setDate(today.getDate() - today.getDay());
          return weekStart;
        }
        case 'month': {
          const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
          return monthStart;
        }
        case 'quarter': {
          const quarter = Math.floor(today.getMonth() / 3);
          const quarterStart = new Date(today.getFullYear(), quarter * 3, 1);
          return quarterStart;
        }
        case 'year': {
          const yearStart = new Date(today.getFullYear(), 0, 1);
          return yearStart;
        }
        default:
          return null;
      }
    }, []);

    const handleShortcut = useCallback((shortcut: DateRange | Date) => {
      let date: Date | null = null;
      
      if (shortcut instanceof Date) {
        date = shortcut;
      } else {
        date = getShortcutDate(shortcut);
      }

      if (date) {
        updateValue(date);
        setCurrentMonth(date);
        setIsPickerOpen(false);
      }
    }, [getShortcutDate, updateValue]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined) {
        const date = externalValue ? new Date(externalValue) : null;
        if (date?.getTime() !== prevValueRef.current?.getTime()) {
          prevValueRef.current = date;
          setDisplayValue(formatDate(date));
          setSelectedDate(date);
          if (date) setCurrentMonth(date);
        }
      }
    }, [externalValue, formatDate]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue && !isControlled) {
        const date = new Date(defaultValue);
        setDisplayValue(formatDate(date));
        setSelectedDate(date);
        setCurrentMonth(date);
        updateValue(date);
      }
    }, [defaultValue, formatDate, updateValue, isControlled]);

    useEffect(() => {
      if (value) {
        setCurrentMonth(value);
      }
    }, [value]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => inputRefInternal.current?.focus(),
      blur: () => inputRefInternal.current?.blur(),
      select: () => inputRefInternal.current?.select(),
      getValue: () => value,
      setValue: (date: Date | null) => updateValue(date),
      openPicker: () => setIsPickerOpen(true),
      closePicker: () => setIsPickerOpen(false),
      validate: () => {
        const validation = validateDate(value);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU DU CALENDRIER
    // ========================================================================

    const renderCalendar = () => {
      const days = getDaysInMonth(currentMonth);
      const monthName = MONTHS[currentMonth.getMonth()];
      const year = currentMonth.getFullYear();

      return (
        <div ref={calendarRef} className="w-full max-w-xs p-3">
          {/* En-tête du calendrier */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-1">
              <button
                type="button"
                className="rounded-lg p-1 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                onClick={() => handleMonthChange(-1)}
              >
                <ChevronLeftIcon className="h-4 w-4" />
              </button>
              <button
                type="button"
                className="rounded-lg px-2 py-1 text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                onClick={() => setViewMode(viewMode === 'days' ? 'months' : 'days')}
              >
                {monthName} {year}
              </button>
              <button
                type="button"
                className="rounded-lg p-1 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                onClick={() => handleMonthChange(1)}
              >
                <ChevronRightIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="flex items-center gap-1">
              {showTodayButton && (
                <Tooltip content="Aujourd'hui">
                  <button
                    type="button"
                    className="rounded-lg p-1 text-xs text-brand-500 hover:bg-brand-50 dark:hover:bg-brand-900/20 transition-colors"
                    onClick={handleToday}
                  >
                    Aujourd'hui
                  </button>
                </Tooltip>
              )}
              {showClearButton && value && (
                <Tooltip content="Effacer">
                  <button
                    type="button"
                    className="rounded-lg p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                    onClick={handleClear}
                  >
                    <XMarkIcon className="h-4 w-4" />
                  </button>
                </Tooltip>
              )}
            </div>
          </div>

          {/* Grille des jours */}
          <div className="grid grid-cols-7 gap-0.5 mb-1">
            {DAYS_OF_WEEK.map((day) => (
              <div key={day} className="text-center text-xs font-medium text-gray-400 dark:text-gray-500 py-1">
                {day}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-0.5">
            {days.map(({ date, day, isCurrentMonth, isToday }) => {
              const isSelected = value && date.toDateString() === value.toDateString();
              const isDisabled = isDateDisabledCheck(date);
              const isPast = date < today;
              const isFuture = date > today;

              return (
                <button
                  key={`${date.getFullYear()}-${date.getMonth()}-${day}`}
                  type="button"
                  className={cn(
                    'aspect-square rounded-lg text-sm transition-colors flex items-center justify-center',
                    !isCurrentMonth && 'text-gray-300 dark:text-gray-600',
                    isToday && 'font-bold text-brand-500',
                    isSelected && 'bg-brand-500 text-white hover:bg-brand-600',
                    !isSelected && !isDisabled && isCurrentMonth && 'hover:bg-gray-100 dark:hover:bg-gray-800',
                    isDisabled && 'opacity-30 cursor-not-allowed',
                    isPast && disablePast && 'opacity-30 cursor-not-allowed',
                    isFuture && disableFuture && 'opacity-30 cursor-not-allowed'
                  )}
                  onClick={() => handleDateSelect(date)}
                  disabled={isDisabled}
                >
                  {day}
                  {isToday && !isSelected && (
                    <span className="absolute bottom-0.5 h-1 w-1 rounded-full bg-brand-500" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Sélecteur de mois/année */}
          {viewMode !== 'days' && (
            <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
              <div className="grid grid-cols-3 gap-1">
                {viewMode === 'months' && (
                  <>
                    {MONTHS.map((month, index) => (
                      <button
                        key={month}
                        type="button"
                        className={cn(
                          'rounded-lg px-2 py-1 text-sm transition-colors',
                          currentMonth.getMonth() === index
                            ? 'bg-brand-500 text-white'
                            : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                        )}
                        onClick={() => {
                          const newDate = new Date(currentMonth);
                          newDate.setMonth(index);
                          setCurrentMonth(newDate);
                          setViewMode('days');
                        }}
                      >
                        {month.slice(0, 3)}
                      </button>
                    ))}
                  </>
                )}
                {viewMode === 'years' && (
                  <>
                    {Array.from({ length: 12 }, (_, i) => {
                      const yearOffset = i - 5;
                      const year = currentMonth.getFullYear() + yearOffset;
                      return (
                        <button
                          key={year}
                          type="button"
                          className={cn(
                            'rounded-lg px-2 py-1 text-sm transition-colors',
                            currentMonth.getFullYear() === year
                              ? 'bg-brand-500 text-white'
                              : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                          )}
                          onClick={() => {
                            const newDate = new Date(currentMonth);
                            newDate.setFullYear(year);
                            setCurrentMonth(newDate);
                            setViewMode('months');
                          }}
                        >
                          {year}
                        </button>
                      );
                    })}
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      );
    };

    // ========================================================================
    // RENDU DES RACCOURCIS
    // ========================================================================

    const renderShortcuts = () => {
      if (!showShortcuts) return null;

      const allShortcuts = shortcuts || DEFAULT_SHORTCUTS;

      return (
        <div className="flex flex-wrap gap-1 p-2 border-t border-gray-200 dark:border-gray-700">
          {allShortcuts.map((shortcut) => (
            <button
              key={shortcut.label}
              type="button"
              className="rounded-lg px-2 py-1 text-xs transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
              onClick={() => handleShortcut(shortcut.value)}
            >
              {shortcut.label}
            </button>
          ))}
        </div>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const hasError = !!error || !isValid || (required && !value);

    return (
      <div ref={containerRef} className="relative space-y-1.5" id={id}>
        {/* Label */}
        {label && (
          <Label 
            htmlFor={id || name} 
            className="text-sm font-medium text-gray-700 dark:text-gray-300"
          >
            {label}
            {required && <span className="ml-1 text-red-500">*</span>}
          </Label>
        )}

        {/* Champ de saisie */}
        <div className="relative">
          <div className={cn(
            'relative flex items-center rounded-lg border transition-all',
            hasError 
              ? 'border-red-500 ring-2 ring-red-500/20 dark:border-red-400' 
              : isValid && value && !disabled
              ? 'border-green-500 ring-2 ring-green-500/20 dark:border-green-400'
              : isFocused
              ? 'border-brand-500 ring-2 ring-brand-500/20 dark:border-brand-400'
              : 'border-gray-300 dark:border-gray-600',
            disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50'
          )}>
            <input
              ref={(node) => {
                inputRefInternal.current = node;
                if (inputRef) {
                  if (typeof inputRef === 'function') {
                    inputRef(node);
                  } else {
                    (inputRef as React.MutableRefObject<HTMLInputElement>).current = node;
                  }
                }
              }}
              id={id || name}
              type="text"
              className={cn(
                'w-full bg-transparent px-3 py-2 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 outline-none',
                disabled && 'cursor-not-allowed'
              )}
              placeholder={placeholder}
              value={displayValue}
              onChange={handleChange}
              onFocus={handleFocus}
              onBlur={handleBlur}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              required={required}
              aria-label={ariaLabel || label}
              aria-describedby={ariaDescribedby}
              aria-invalid={hasError}
              aria-required={required}
              name={name}
            />

            {/* Icône calendrier */}
            {showPicker && !disabled && (
              <button
                type="button"
                className="flex-shrink-0 pr-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                onClick={() => setIsPickerOpen(!isPickerOpen)}
              >
                <CalendarIcon className="h-5 w-5" />
              </button>
            )}
          </div>

          {/* Popover du calendrier */}
          {showPicker && (
            <Popover
              open={isPickerOpen}
              onOpenChange={setIsPickerOpen}
              trigger={<div className="hidden" />}
              placement="bottom-start"
              className="z-50"
            >
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg">
                {renderCalendar()}
                {renderShortcuts()}
              </div>
            </Popover>
          )}

          {/* Statut */}
          <div className="mt-1 flex items-center gap-1.5 text-xs">
            {hasError && (
              <span className="text-red-600 dark:text-red-400">
                {error || validationMessage}
              </span>
            )}
            {success && !hasError && (
              <span className="text-green-600 dark:text-green-400">{success}</span>
            )}
            {info && !hasError && !success && (
              <span className="text-blue-600 dark:text-blue-400">{info}</span>
            )}
          </div>
        </div>

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}
      </div>
    );
  }
);

DateField.displayName = 'DateField';

// ============================================================================
// EXPORTS
// ============================================================================

export default DateField;

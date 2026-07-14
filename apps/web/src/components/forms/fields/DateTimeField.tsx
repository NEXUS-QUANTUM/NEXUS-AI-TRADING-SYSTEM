// apps/web/src/components/forms/fields/DateTimeField.tsx
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
  ClockIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  XMarkIcon,
  CheckIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  PlusIcon,
  MinusIcon,
  SunIcon,
  MoonIcon,
  GlobeAltIcon,
  AdjustmentsHorizontalIcon,
  ArrowPathIcon as RefreshIcon,
} from '@heroicons/react/24/outline';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';
import { Popover } from '@/components/common/Popover';
import { Select } from '@/components/common/Select';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type DateTimeFormat = 
  | 'dd/MM/yyyy HH:mm'
  | 'MM/dd/yyyy HH:mm'
  | 'yyyy-MM-dd HH:mm'
  | 'dd-MM-yyyy HH:mm'
  | 'dd/MM/yyyy HH:mm:ss'
  | 'MM/dd/yyyy HH:mm:ss'
  | 'yyyy-MM-dd HH:mm:ss'
  | 'dd/MM/yyyy hh:mm a'
  | 'MM/dd/yyyy hh:mm a'
  | 'yyyy-MM-dd hh:mm a'
  | 'dd/MM/yyyy HH:mm:ss.SSS'
  | 'ISO';

export type TimeFormat = '12h' | '24h';
export type Timezone = 'UTC' | 'local' | string;
export type DateTimePickerVariant = 'default' | 'compact' | 'minimal' | 'rounded' | 'outlined';

export interface DateTimeFieldProps {
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
  dateFormat?: DateTimeFormat;
  /** Format de l'heure */
  timeFormat?: TimeFormat;
  /** Timezone */
  timezone?: Timezone;
  /** Variante du picker */
  variant?: DateTimePickerVariant;
  /** Afficher le sélecteur de date */
  showDatePicker?: boolean;
  /** Afficher le sélecteur d'heure */
  showTimePicker?: boolean;
  /** Afficher le sélecteur de timezone */
  showTimezone?: boolean;
  /** Afficher le bouton "Maintenant" */
  showNowButton?: boolean;
  /** Afficher le bouton "Effacer" */
  showClearButton?: boolean;
  /** Afficher les secondes */
  showSeconds?: boolean;
  /** Afficher les millisecondes */
  showMilliseconds?: boolean;

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
  /** Heure minimale (HH:mm) */
  minTime?: string;
  /** Heure maximale (HH:mm) */
  maxTime?: string;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;

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

const DATE_FORMATS: Record<DateTimeFormat, { format: string; separator: string; order: ('d' | 'm' | 'y' | 'h' | 'min' | 's' | 'ms' | 'a')[]; hasTime: boolean; hasSeconds: boolean; hasMilliseconds: boolean; is12h: boolean }> = {
  'dd/MM/yyyy HH:mm': { 
    format: 'dd/MM/yyyy HH:mm', 
    separator: '/', 
    order: ['d', 'm', 'y', 'h', 'min'], 
    hasTime: true, 
    hasSeconds: false, 
    hasMilliseconds: false, 
    is12h: false 
  },
  'MM/dd/yyyy HH:mm': { 
    format: 'MM/dd/yyyy HH:mm', 
    separator: '/', 
    order: ['m', 'd', 'y', 'h', 'min'], 
    hasTime: true, 
    hasSeconds: false, 
    hasMilliseconds: false, 
    is12h: false 
  },
  'yyyy-MM-dd HH:mm': { 
    format: 'yyyy-MM-dd HH:mm', 
    separator: '-', 
    order: ['y', 'm', 'd', 'h', 'min'], 
    hasTime: true, 
    hasSeconds: false, 
    hasMilliseconds: false, 
    is12h: false 
  },
  'dd-MM-yyyy HH:mm': { 
    format: 'dd-MM-yyyy HH:mm', 
    separator: '-', 
    order: ['d', 'm', 'y', 'h', 'min'], 
    hasTime: true, 
    hasSeconds: false, 
    hasMilliseconds: false, 
    is12h: false 
  },
  'dd/MM/yyyy HH:mm:ss': { 
    format: 'dd/MM/yyyy HH:mm:ss', 
    separator: '/', 
    order: ['d', 'm', 'y', 'h', 'min', 's'], 
    hasTime: true, 
    hasSeconds: true, 
    hasMilliseconds: false, 
    is12h: false 
  },
  'MM/dd/yyyy HH:mm:ss': { 
    format: 'MM/dd/yyyy HH:mm:ss', 
    separator: '/', 
    order: ['m', 'd', 'y', 'h', 'min', 's'], 
    hasTime: true, 
    hasSeconds: true, 
    hasMilliseconds: false, 
    is12h: false 
  },
  'yyyy-MM-dd HH:mm:ss': { 
    format: 'yyyy-MM-dd HH:mm:ss', 
    separator: '-', 
    order: ['y', 'm', 'd', 'h', 'min', 's'], 
    hasTime: true, 
    hasSeconds: true, 
    hasMilliseconds: false, 
    is12h: false 
  },
  'dd/MM/yyyy hh:mm a': { 
    format: 'dd/MM/yyyy hh:mm a', 
    separator: '/', 
    order: ['d', 'm', 'y', 'h', 'min', 'a'], 
    hasTime: true, 
    hasSeconds: false, 
    hasMilliseconds: false, 
    is12h: true 
  },
  'MM/dd/yyyy hh:mm a': { 
    format: 'MM/dd/yyyy hh:mm a', 
    separator: '/', 
    order: ['m', 'd', 'y', 'h', 'min', 'a'], 
    hasTime: true, 
    hasSeconds: false, 
    hasMilliseconds: false, 
    is12h: true 
  },
  'yyyy-MM-dd hh:mm a': { 
    format: 'yyyy-MM-dd hh:mm a', 
    separator: '-', 
    order: ['y', 'm', 'd', 'h', 'min', 'a'], 
    hasTime: true, 
    hasSeconds: false, 
    hasMilliseconds: false, 
    is12h: true 
  },
  'dd/MM/yyyy HH:mm:ss.SSS': { 
    format: 'dd/MM/yyyy HH:mm:ss.SSS', 
    separator: '/', 
    order: ['d', 'm', 'y', 'h', 'min', 's', 'ms'], 
    hasTime: true, 
    hasSeconds: true, 
    hasMilliseconds: true, 
    is12h: false 
  },
  'ISO': { 
    format: 'ISO', 
    separator: '-', 
    order: ['y', 'm', 'd', 'h', 'min', 's', 'ms'], 
    hasTime: true, 
    hasSeconds: true, 
    hasMilliseconds: true, 
    is12h: false 
  },
};

const TIMEZONES: { value: string; label: string; offset: string }[] = [
  { value: 'UTC', label: 'UTC', offset: '+00:00' },
  { value: 'Europe/Paris', label: 'Paris', offset: '+01:00' },
  { value: 'Europe/London', label: 'Londres', offset: '+00:00' },
  { value: 'America/New_York', label: 'New York', offset: '-05:00' },
  { value: 'America/Chicago', label: 'Chicago', offset: '-06:00' },
  { value: 'America/Los_Angeles', label: 'Los Angeles', offset: '-08:00' },
  { value: 'Asia/Tokyo', label: 'Tokyo', offset: '+09:00' },
  { value: 'Asia/Singapore', label: 'Singapour', offset: '+08:00' },
  { value: 'Australia/Sydney', label: 'Sydney', offset: '+11:00' },
  { value: 'Europe/Moscow', label: 'Moscou', offset: '+03:00' },
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const DateTimeField = forwardRef<HTMLInputElement, DateTimeFieldProps>(
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
      placeholder = 'Sélectionner date et heure',
      description,
      error,
      success,
      info,
      dateFormat = 'dd/MM/yyyy HH:mm',
      timeFormat = '24h',
      timezone = 'local',
      variant = 'default',
      showDatePicker = true,
      showTimePicker = true,
      showTimezone = true,
      showNowButton = true,
      showClearButton = true,
      showSeconds = false,
      showMilliseconds = false,

      // Comportement
      disabled = false,
      required = false,
      disablePast = false,
      disableFuture = false,
      minDate,
      maxDate,
      minTime,
      maxTime,
      disableRealtimeValidation = false,

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
    const [currentDate, setCurrentDate] = useState<Date>(new Date());
    const [selectedDate, setSelectedDate] = useState<Date | null>(
      defaultValue ? new Date(defaultValue) : null
    );
    const [selectedTime, setSelectedTime] = useState<{ hours: number; minutes: number; seconds: number; milliseconds: number }>({
      hours: 0,
      minutes: 0,
      seconds: 0,
      milliseconds: 0,
    });
    const [isPickerOpen, setIsPickerOpen] = useState(false);
    const [viewMode, setViewMode] = useState<'days' | 'months' | 'years'>('days');
    const [selectedTimezone, setSelectedTimezone] = useState<string>(timezone);
    const [tempDate, setTempDate] = useState<Date | null>(null);
    const [isEditingTime, setIsEditingTime] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? (externalValue ? new Date(externalValue) : null) : internalValue;
    const isControlled = externalValue !== undefined;
    const formatInfo = DATE_FORMATS[dateFormat] || DATE_FORMATS['dd/MM/yyyy HH:mm'];
    const minDateObj = minDate ? new Date(minDate) : null;
    const maxDateObj = maxDate ? new Date(maxDate) : null;
    const today = new Date();
    const is12h = timeFormat === '12h' || formatInfo.is12h;

    // ========================================================================
    // FORMATAGE
    // ========================================================================

    const formatDateTime = useCallback((date: Date | null): string => {
      if (!date) return '';

      if (customFormat) {
        return customFormat(date);
      }

      if (dateFormat === 'ISO') {
        return date.toISOString();
      }

      const d = date.getDate().toString().padStart(2, '0');
      const m = (date.getMonth() + 1).toString().padStart(2, '0');
      const y = date.getFullYear().toString();
      let h = date.getHours();
      const min = date.getMinutes().toString().padStart(2, '0');
      const s = date.getSeconds().toString().padStart(2, '0');
      const ms = date.getMilliseconds().toString().padStart(3, '0');

      let ampm = '';
      if (is12h) {
        ampm = h >= 12 ? 'PM' : 'AM';
        h = h % 12 || 12;
      }
      const hStr = h.toString().padStart(2, '0');

      const parts: Record<string, string> = { d, m, y, h: hStr, min, s, ms, a: ampm };
      const orderedParts = formatInfo.order.map(key => parts[key]);

      return orderedParts.join(formatInfo.separator);
    }, [dateFormat, is12h, customFormat, formatInfo]);

    const parseDateTime = useCallback((text: string): Date | null => {
      if (!text || text.trim() === '') return null;

      if (customParse) {
        return customParse(text);
      }

      if (dateFormat === 'ISO') {
        const date = new Date(text);
        return isNaN(date.getTime()) ? null : date;
      }

      const cleaned = text.replace(/\s/g, '');
      const parts = cleaned.split(new RegExp(`[${formatInfo.separator}/.: ]`));
      
      if (parts.length < 3) return null;

      const values: Record<string, number> = {};
      const order = formatInfo.order;

      for (let i = 0; i < Math.min(parts.length, order.length); i++) {
        const key = order[i];
        let val = parseInt(parts[i]);
        if (isNaN(val)) return null;
        
        // Gérer AM/PM
        if (key === 'a') {
          const isPM = parts[i].toUpperCase().includes('PM');
          if (isPM && values.h < 12) values.h += 12;
          if (!isPM && values.h === 12) values.h = 0;
          continue;
        }

        values[key] = val;
      }

      // Ajuster l'année si 2 chiffres
      let year = values.y || 0;
      if (year < 100) {
        year += year >= 50 ? 1900 : 2000;
      }

      const month = (values.m || 1) - 1;
      const day = values.d || 1;
      const hours = values.h || 0;
      const minutes = values.min || 0;
      const seconds = values.s || 0;
      const milliseconds = values.ms || 0;

      const date = new Date(year, month, day, hours, minutes, seconds, milliseconds);
      if (isNaN(date.getTime())) return null;

      return date;
    }, [dateFormat, customParse, formatInfo]);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateDateTime = useCallback((date: Date | null): { valid: boolean; message: string } => {
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
        return { valid: false, message: `La date minimale est ${formatDateTime(minDateObj)}` };
      }

      // Vérifier la date maximale
      if (maxDateObj && d > maxDateObj) {
        return { valid: false, message: `La date maximale est ${formatDateTime(maxDateObj)}` };
      }

      // Vérifier l'heure minimale
      if (minTime) {
        const [minH, minM] = minTime.split(':').map(Number);
        const hour = d.getHours();
        const minute = d.getMinutes();
        if (hour < minH || (hour === minH && minute < minM)) {
          return { valid: false, message: `L'heure minimale est ${minTime}` };
        }
      }

      // Vérifier l'heure maximale
      if (maxTime) {
        const [maxH, maxM] = maxTime.split(':').map(Number);
        const hour = d.getHours();
        const minute = d.getMinutes();
        if (hour > maxH || (hour === maxH && minute > maxM)) {
          return { valid: false, message: `L'heure maximale est ${maxTime}` };
        }
      }

      return { valid: true, message: '' };
    }, [
      required,
      disablePast,
      disableFuture,
      minDateObj,
      maxDateObj,
      minTime,
      maxTime,
      formatDateTime,
      today,
      customValidate,
    ]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((date: Date | null) => {
      const validation = validateDateTime(date);
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

      const formatted = formatDateTime(date);
      setDisplayValue(formatted);
      setSelectedDate(date);

      if (date) {
        setSelectedTime({
          hours: date.getHours(),
          minutes: date.getMinutes(),
          seconds: date.getSeconds(),
          milliseconds: date.getMilliseconds(),
        });
      }

      if (debug) {
        console.log('DateTimeField update:', { date, formatted, isValid: validation.valid });
      }
    }, [
      formatDateTime,
      validateDateTime,
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
        const parsed = parseDateTime(rawValue);
        const validation = validateDateTime(parsed);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        if (onValidate) onValidate(validation.valid, parsed);
      }
    }, [disableRealtimeValidation, parseDateTime, validateDateTime, onValidate]);

    const handleFocus = useCallback(() => {
      setIsFocused(true);
      if (onFocus) onFocus();
    }, [onFocus]);

    const handleBlur = useCallback(() => {
      setIsFocused(false);

      const parsed = parseDateTime(displayValue);
      const validation = validateDateTime(parsed);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);
      if (onValidate) onValidate(validation.valid, parsed);

      if (parsed) {
        updateValue(parsed);
      } else if (!displayValue) {
        updateValue(null);
      } else {
        setDisplayValue(formatDateTime(value));
      }

      if (onBlur) onBlur();
    }, [parseDateTime, validateDateTime, onValidate, updateValue, formatDateTime, value, displayValue, onBlur]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const parsed = parseDateTime(displayValue);
        if (parsed) {
          updateValue(parsed);
        }
        inputRefInternal.current?.blur();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setDisplayValue(formatDateTime(value));
        inputRefInternal.current?.blur();
      }
    }, [displayValue, parseDateTime, updateValue, formatDateTime, value]);

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
      const todayDate = new Date();
      todayDate.setHours(0, 0, 0, 0);

      // Jours du mois précédent
      const prevMonthLastDay = new Date(year, month, 0).getDate();
      for (let i = startDayOfWeek - 1; i >= 0; i--) {
        const day = prevMonthLastDay - i;
        const dateObj = new Date(year, month - 1, day);
        days.push({ date: dateObj, day, isCurrentMonth: false, isToday: false });
      }

      // Jours du mois courant
      for (let i = 1; i <= daysInMonth; i++) {
        const dateObj = new Date(year, month, i);
        const isToday = dateObj.toDateString() === todayDate.toDateString();
        days.push({ date: dateObj, day: i, isCurrentMonth: true, isToday });
      }

      // Jours du mois suivant
      const remainingDays = 42 - days.length;
      for (let i = 1; i <= remainingDays; i++) {
        const dateObj = new Date(year, month + 1, i);
        days.push({ date: dateObj, day: i, isCurrentMonth: false, isToday: false });
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
      
      return false;
    }, [isDateDisabled, disablePast, disableFuture, minDateObj, maxDateObj, today]);

    const handleDateSelect = useCallback((date: Date) => {
      if (isDateDisabledCheck(date)) return;
      
      const selected = new Date(date);
      // Conserver l'heure actuelle
      const currentTime = value || new Date();
      selected.setHours(currentTime.getHours(), currentTime.getMinutes(), currentTime.getSeconds(), currentTime.getMilliseconds());
      
      updateValue(selected);
      setCurrentDate(selected);
    }, [isDateDisabledCheck, value, updateValue]);

    const handleMonthChange = useCallback((delta: number) => {
      const newDate = new Date(currentDate);
      newDate.setMonth(newDate.getMonth() + delta);
      setCurrentDate(newDate);
    }, [currentDate]);

    // ========================================================================
    // SÉLECTEUR D'HEURE
    // ========================================================================

    const handleTimeChange = useCallback((type: 'hours' | 'minutes' | 'seconds' | 'milliseconds', value: number) => {
      const newDate = value ? new Date(value) : new Date();
      if (!newDate) return;

      const current = value || new Date();
      
      let hours = current.getHours();
      let minutes = current.getMinutes();
      let seconds = current.getSeconds();
      let milliseconds = current.getMilliseconds();

      switch (type) {
        case 'hours':
          hours = Math.max(0, Math.min(23, value));
          break;
        case 'minutes':
          minutes = Math.max(0, Math.min(59, value));
          break;
        case 'seconds':
          seconds = Math.max(0, Math.min(59, value));
          break;
        case 'milliseconds':
          milliseconds = Math.max(0, Math.min(999, value));
          break;
      }

      const newDateObj = new Date(current);
      newDateObj.setHours(hours, minutes, seconds, milliseconds);
      
      updateValue(newDateObj);
      setSelectedTime({ hours, minutes, seconds, milliseconds });
    }, [value, updateValue]);

    // ========================================================================
    // TIMEZONE
    // ========================================================================

    const handleTimezoneChange = useCallback((tz: string) => {
      setSelectedTimezone(tz);
      
      if (value) {
        const currentDate = new Date(value);
        // Appliquer le décalage horaire
        // Note: Dans une implémentation réelle, on utiliserait des librairies comme moment-timezone
        updateValue(currentDate);
      }
      
      if (debug) {
        console.log('Timezone changed:', tz);
      }
    }, [value, updateValue, debug]);

    // ========================================================================
    // RACCOURCIS
    // ========================================================================

    const handleNow = useCallback(() => {
      const now = new Date();
      updateValue(now);
      setCurrentDate(now);
      setIsPickerOpen(false);
    }, [updateValue]);

    const handleClear = useCallback(() => {
      updateValue(null);
      setDisplayValue('');
      setIsPickerOpen(false);
    }, [updateValue]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined) {
        const date = externalValue ? new Date(externalValue) : null;
        if (date?.getTime() !== prevValueRef.current?.getTime()) {
          prevValueRef.current = date;
          setDisplayValue(formatDateTime(date));
          setSelectedDate(date);
          if (date) {
            setCurrentDate(date);
            setSelectedTime({
              hours: date.getHours(),
              minutes: date.getMinutes(),
              seconds: date.getSeconds(),
              milliseconds: date.getMilliseconds(),
            });
          }
        }
      }
    }, [externalValue, formatDateTime]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue && !isControlled) {
        const date = new Date(defaultValue);
        setDisplayValue(formatDateTime(date));
        setSelectedDate(date);
        setCurrentDate(date);
        setSelectedTime({
          hours: date.getHours(),
          minutes: date.getMinutes(),
          seconds: date.getSeconds(),
          milliseconds: date.getMilliseconds(),
        });
        updateValue(date);
      }
    }, [defaultValue, formatDateTime, updateValue, isControlled]);

    useEffect(() => {
      if (value) {
        setCurrentDate(value);
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
        const validation = validateDateTime(value);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU DU CALENDRIER
    // ========================================================================

    const renderCalendar = () => {
      const days = getDaysInMonth(currentDate);
      const monthName = MONTHS[currentDate.getMonth()];
      const year = currentDate.getFullYear();

      return (
        <div className="w-full max-w-xs p-3">
          {/* En-tête */}
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
              {showNowButton && (
                <Tooltip content="Maintenant">
                  <button
                    type="button"
                    className="rounded-lg p-1 text-xs text-brand-500 hover:bg-brand-50 dark:hover:bg-brand-900/20 transition-colors"
                    onClick={handleNow}
                  >
                    Maintenant
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

          {/* Jours de la semaine */}
          <div className="grid grid-cols-7 gap-0.5 mb-1">
            {DAYS_OF_WEEK.map((day) => (
              <div key={day} className="text-center text-xs font-medium text-gray-400 dark:text-gray-500 py-1">
                {day}
              </div>
            ))}
          </div>

          {/* Grille des jours */}
          <div className="grid grid-cols-7 gap-0.5">
            {days.map(({ date, day, isCurrentMonth, isToday }) => {
              const isSelected = value && date.toDateString() === value.toDateString();
              const isDisabled = isDateDisabledCheck(date);

              return (
                <button
                  key={`${date.getFullYear()}-${date.getMonth()}-${day}`}
                  type="button"
                  className={cn(
                    'aspect-square rounded-lg text-sm transition-colors flex items-center justify-center relative',
                    !isCurrentMonth && 'text-gray-300 dark:text-gray-600',
                    isToday && 'font-bold text-brand-500',
                    isSelected && 'bg-brand-500 text-white hover:bg-brand-600',
                    !isSelected && !isDisabled && isCurrentMonth && 'hover:bg-gray-100 dark:hover:bg-gray-800',
                    isDisabled && 'opacity-30 cursor-not-allowed'
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
                          currentDate.getMonth() === index
                            ? 'bg-brand-500 text-white'
                            : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                        )}
                        onClick={() => {
                          const newDate = new Date(currentDate);
                          newDate.setMonth(index);
                          setCurrentDate(newDate);
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
                      const year = currentDate.getFullYear() + yearOffset;
                      return (
                        <button
                          key={year}
                          type="button"
                          className={cn(
                            'rounded-lg px-2 py-1 text-sm transition-colors',
                            currentDate.getFullYear() === year
                              ? 'bg-brand-500 text-white'
                              : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                          )}
                          onClick={() => {
                            const newDate = new Date(currentDate);
                            newDate.setFullYear(year);
                            setCurrentDate(newDate);
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
    // RENDU DU SÉLECTEUR D'HEURE
    // ========================================================================

    const renderTimePicker = () => {
      if (!showTimePicker) return null;

      const currentTime = value || new Date();
      const hours = currentTime.getHours();
      const minutes = currentTime.getMinutes();
      const seconds = currentTime.getSeconds();
      const milliseconds = currentTime.getMilliseconds();

      const hourDisplay = is12h ? (hours % 12 || 12) : hours;
      const ampm = hours >= 12 ? 'PM' : 'AM';

      return (
        <div className="p-3 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 justify-center">
            {/* Heures */}
            <div className="flex flex-col items-center">
              <button
                type="button"
                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                onClick={() => handleTimeChange('hours', hours + 1)}
              >
                <ChevronUpIcon className="h-4 w-4" />
              </button>
              <span className="text-xl font-mono font-medium min-w-[2.5rem] text-center">
                {hourDisplay.toString().padStart(2, '0')}
              </span>
              <button
                type="button"
                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                onClick={() => handleTimeChange('hours', hours - 1)}
              >
                <ChevronDownIcon className="h-4 w-4" />
              </button>
            </div>

            <span className="text-xl font-mono font-medium">:</span>

            {/* Minutes */}
            <div className="flex flex-col items-center">
              <button
                type="button"
                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                onClick={() => handleTimeChange('minutes', minutes + 1)}
              >
                <ChevronUpIcon className="h-4 w-4" />
              </button>
              <span className="text-xl font-mono font-medium min-w-[2.5rem] text-center">
                {minutes.toString().padStart(2, '0')}
              </span>
              <button
                type="button"
                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                onClick={() => handleTimeChange('minutes', minutes - 1)}
              >
                <ChevronDownIcon className="h-4 w-4" />
              </button>
            </div>

            {/* Secondes */}
            {showSeconds && (
              <>
                <span className="text-xl font-mono font-medium">:</span>
                <div className="flex flex-col items-center">
                  <button
                    type="button"
                    className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    onClick={() => handleTimeChange('seconds', seconds + 1)}
                  >
                    <ChevronUpIcon className="h-4 w-4" />
                  </button>
                  <span className="text-xl font-mono font-medium min-w-[2.5rem] text-center">
                    {seconds.toString().padStart(2, '0')}
                  </span>
                  <button
                    type="button"
                    className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    onClick={() => handleTimeChange('seconds', seconds - 1)}
                  >
                    <ChevronDownIcon className="h-4 w-4" />
                  </button>
                </div>
              </>
            )}

            {/* AM/PM pour 12h */}
            {is12h && (
              <div className="ml-2 flex flex-col gap-1">
                <button
                  type="button"
                  className={cn(
                    'rounded px-2 py-1 text-xs font-medium transition-colors',
                    ampm === 'AM' ? 'bg-brand-500 text-white' : 'bg-gray-200 dark:bg-gray-700'
                  )}
                  onClick={() => {
                    const newHours = hours >= 12 ? hours - 12 : hours;
                    handleTimeChange('hours', newHours);
                  }}
                >
                  AM
                </button>
                <button
                  type="button"
                  className={cn(
                    'rounded px-2 py-1 text-xs font-medium transition-colors',
                    ampm === 'PM' ? 'bg-brand-500 text-white' : 'bg-gray-200 dark:bg-gray-700'
                  )}
                  onClick={() => {
                    const newHours = hours < 12 ? hours + 12 : hours;
                    handleTimeChange('hours', newHours);
                  }}
                >
                  PM
                </button>
              </div>
            )}
          </div>

          {/* Millisecondes */}
          {showMilliseconds && (
            <div className="mt-2 flex items-center justify-center gap-2">
              <span className="text-xs text-gray-500 dark:text-gray-400">MS</span>
              <input
                type="range"
                min="0"
                max="999"
                value={milliseconds}
                onChange={(e) => handleTimeChange('milliseconds', parseInt(e.target.value))}
                className="w-32"
              />
              <span className="text-xs font-mono min-w-[2.5rem] text-center">
                {milliseconds.toString().padStart(3, '0')}
              </span>
            </div>
          )}
        </div>
      );
    };

    // ========================================================================
    // RENDU DU SÉLECTEUR DE TIMEZONE
    // ========================================================================

    const renderTimezoneSelector = () => {
      if (!showTimezone) return null;

      return (
        <div className="p-2 border-t border-gray-200 dark:border-gray-700">
          <Select
            options={TIMEZONES.map(tz => ({
              value: tz.value,
              label: `${tz.label} (${tz.offset})`,
            }))}
            value={selectedTimezone}
            onChange={handleTimezoneChange}
            size="sm"
            className="w-full"
            placeholder="Fuseau horaire"
          />
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

            {/* Icônes */}
            <div className="flex items-center gap-1 pr-2">
              {showTimezone && (
                <Tooltip content={`Timezone: ${selectedTimezone}`}>
                  <GlobeAltIcon className="h-4 w-4 text-gray-400" />
                </Tooltip>
              )}
              {showDatePicker && !disabled && (
                <button
                  type="button"
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors p-1"
                  onClick={() => setIsPickerOpen(!isPickerOpen)}
                >
                  <CalendarIcon className="h-5 w-5" />
                </button>
              )}
            </div>
          </div>

          {/* Popover */}
          {showDatePicker && (
            <Popover
              open={isPickerOpen}
              onOpenChange={setIsPickerOpen}
              trigger={<div className="hidden" />}
              placement="bottom-start"
              className="z-50"
            >
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg max-w-sm">
                {renderCalendar()}
                {renderTimePicker()}
                {renderTimezoneSelector()}
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

DateTimeField.displayName = 'DateTimeField';

// ============================================================================
// EXPORTS
// ============================================================================

export default DateTimeField;

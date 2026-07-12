/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import { cn } from '@/utils/helpers';
import { Button } from './Button';
import { Calendar } from './Calendar';
import { Popover, PopoverContent, PopoverTrigger } from './Popover';
import { Input } from './Input';
import { Label } from './Label';
import {
  CalendarIcon,
  Clock,
  ChevronLeft,
  ChevronRight,
  X,
  Calendar as CalendarIcon2,
} from 'lucide-react';
import { format, parse, isValid, isAfter, isBefore, isEqual } from 'date-fns';
import { fr, enUS, es, de, zhCN, ja } from 'date-fns/locale';

// ============================================
// TYPES
// ============================================

export interface DatePickerProps {
  value?: Date;
  onChange?: (date: Date | undefined) => void;
  onSelect?: (date: Date) => void;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  minDate?: Date;
  maxDate?: Date;
  disabledDates?: Date[];
  highlightedDates?: Date[];
  format?: string;
  locale?: 'fr' | 'en' | 'es' | 'de' | 'zh' | 'ja';
  className?: string;
  inputClassName?: string;
  popoverClassName?: string;
  showTime?: boolean;
  timeFormat?: '12h' | '24h';
  timeStep?: number;
  showClear?: boolean;
  showToday?: boolean;
  showWeekNumbers?: boolean;
  firstDayOfWeek?: 0 | 1 | 2 | 3 | 4 | 5 | 6;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'outline' | 'ghost' | 'filled';
  error?: string;
  label?: string;
  description?: string;
  required?: boolean;
  disabled?: boolean;
  id?: string;
  name?: string;
  autoFocus?: boolean;
  onFocus?: () => void;
  onBlur?: () => void;
}

// ============================================
// CONSTANTES
// ============================================

const LOCALES = {
  fr: fr,
  en: enUS,
  es: es,
  de: de,
  zh: zhCN,
  ja: ja,
};

const DEFAULT_FORMATS = {
  fr: 'dd/MM/yyyy',
  en: 'MM/dd/yyyy',
  es: 'dd/MM/yyyy',
  de: 'dd.MM.yyyy',
  zh: 'yyyy/MM/dd',
  ja: 'yyyy/MM/dd',
};

const TIME_FORMATS = {
  '12h': 'hh:mm a',
  '24h': 'HH:mm',
};

// ============================================
// COMPOSANT
// ============================================

export function DatePicker({
  value,
  onChange,
  onSelect,
  placeholder = 'Sélectionner une date',
  disabled = false,
  required = false,
  minDate,
  maxDate,
  disabledDates = [],
  highlightedDates = [],
  format: formatProp,
  locale = 'fr',
  className,
  inputClassName,
  popoverClassName,
  showTime = false,
  timeFormat = '24h',
  timeStep = 15,
  showClear = true,
  showToday = true,
  showWeekNumbers = false,
  firstDayOfWeek = 1,
  size = 'md',
  variant = 'default',
  error,
  label,
  description,
  id,
  name,
  autoFocus,
  onFocus,
  onBlur,
}: DatePickerProps) {
  // ============================================
  // RÉFÉRENCES
  // ============================================
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [isOpen, setIsOpen] = React.useState(false);

  // ============================================
  // ÉTATS
  // ============================================
  const [selectedDate, setSelectedDate] = React.useState<Date | undefined>(value);
  const [inputValue, setInputValue] = React.useState<string>('');
  const [timeValue, setTimeValue] = React.useState<string>('');

  const dateFormat = formatProp || DEFAULT_FORMATS[locale] || 'dd/MM/yyyy';
  const localeObj = LOCALES[locale] || fr;

  // ============================================
  // EFFETS
  // ============================================

  React.useEffect(() => {
    setSelectedDate(value);
    if (value && isValid(value)) {
      setInputValue(format(value, dateFormat, { locale: localeObj }));
      if (showTime) {
        setTimeValue(format(value, TIME_FORMATS[timeFormat]));
      }
    } else {
      setInputValue('');
      setTimeValue('');
    }
  }, [value, dateFormat, localeObj, showTime, timeFormat]);

  // ============================================
  // FONCTIONS
  // ============================================

  const handleDateSelect = (date: Date) => {
    if (!date || !isValid(date)) return;

    let newDate = new Date(date);

    // Ajouter l'heure si elle est définie
    if (showTime && timeValue) {
      try {
        const timeParts = timeValue.match(/(\d+):(\d+)(?:\s*(am|pm))?/i);
        if (timeParts) {
          let hours = parseInt(timeParts[1]);
          const minutes = parseInt(timeParts[2]);
          const ampm = timeParts[3]?.toLowerCase();

          if (timeFormat === '12h' && ampm) {
            if (ampm === 'pm' && hours !== 12) hours += 12;
            if (ampm === 'am' && hours === 12) hours = 0;
          }

          newDate.setHours(hours, minutes, 0, 0);
        }
      } catch (error) {
        // Ignorer les erreurs de parsing
      }
    }

    setSelectedDate(newDate);
    setInputValue(format(newDate, dateFormat, { locale: localeObj }));
    onChange?.(newDate);
    onSelect?.(newDate);
    setIsOpen(false);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInputValue(value);

    try {
      const parsedDate = parse(value, dateFormat, new Date(), { locale: localeObj });
      if (isValid(parsedDate)) {
        setSelectedDate(parsedDate);
        onChange?.(parsedDate);
        onSelect?.(parsedDate);
      }
    } catch (error) {
      // Ignorer les erreurs de parsing
    }
  };

  const handleTimeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setTimeValue(value);

    if (selectedDate && isValid(selectedDate)) {
      try {
        const timeParts = value.match(/(\d+):(\d+)(?:\s*(am|pm))?/i);
        if (timeParts) {
          let hours = parseInt(timeParts[1]);
          const minutes = parseInt(timeParts[2]);
          const ampm = timeParts[3]?.toLowerCase();

          if (timeFormat === '12h' && ampm) {
            if (ampm === 'pm' && hours !== 12) hours += 12;
            if (ampm === 'am' && hours === 12) hours = 0;
          }

          const newDate = new Date(selectedDate);
          newDate.setHours(hours, minutes, 0, 0);
          setSelectedDate(newDate);
          onChange?.(newDate);
        }
      } catch (error) {
        // Ignorer les erreurs de parsing
      }
    }
  };

  const handleClear = () => {
    setSelectedDate(undefined);
    setInputValue('');
    setTimeValue('');
    onChange?.(undefined);
    onSelect?.(undefined as any);
    setIsOpen(false);
  };

  const handleToday = () => {
    const today = new Date();
    handleDateSelect(today);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      setIsOpen(true);
    }
    if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  // ============================================
  // TAILLES
  // ============================================

  const sizeClasses = {
    sm: 'h-8 text-xs',
    md: 'h-10 text-sm',
    lg: 'h-12 text-base',
  };

  const variantClasses = {
    default: 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900',
    outline: 'border-2 border-gray-300 dark:border-gray-600 bg-transparent',
    ghost: 'border-transparent bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800',
    filled: 'border-transparent bg-gray-100 dark:bg-gray-800',
  };

  // ============================================
  // RENDU
  // ============================================

  const datePickerId = id || `datepicker-${React.useId()}`;
  const errorId = `${datePickerId}-error`;
  const descriptionId = `${datePickerId}-description`;

  return (
    <div className={cn('w-full', className)}>
      {/* Label */}
      {label && (
        <Label
          htmlFor={datePickerId}
          className={cn(
            'mb-2 block text-sm font-medium text-gray-700 dark:text-gray-300',
            required && 'after:ml-0.5 after:text-red-500 after:content-["*"]'
          )}
        >
          {label}
        </Label>
      )}

      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger asChild>
          <button
            id={datePickerId}
            type="button"
            className={cn(
              'flex w-full items-center justify-between rounded-md border px-3 py-2 text-sm',
              'transition-colors duration-200',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2',
              'disabled:cursor-not-allowed disabled:opacity-50',
              sizeClasses[size],
              variantClasses[variant],
              error && 'border-red-500 ring-1 ring-red-500',
              !selectedDate && 'text-gray-400 dark:text-gray-500',
              className
            )}
            disabled={disabled}
            onFocus={onFocus}
            onBlur={onBlur}
            aria-invalid={!!error}
            aria-describedby={error ? errorId : description ? descriptionId : undefined}
          >
            <span className="flex items-center gap-2">
              <CalendarIcon2 className="h-4 w-4 flex-shrink-0" />
              <span className="truncate">
                {selectedDate && isValid(selectedDate)
                  ? format(selectedDate, dateFormat, { locale: localeObj })
                  : placeholder}
              </span>
              {showTime && selectedDate && isValid(selectedDate) && (
                <span className="text-gray-400 dark:text-gray-500">
                  {format(selectedDate, TIME_FORMATS[timeFormat])}
                </span>
              )}
            </span>
            {selectedDate && showClear && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleClear();
                }}
                className="rounded-full p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-300"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </button>
        </PopoverTrigger>

        <PopoverContent
          className={cn('w-auto p-0', popoverClassName)}
          align="start"
          sideOffset={4}
        >
          <div className="p-3">
            <Calendar
              value={selectedDate}
              onChange={handleDateSelect}
              minDate={minDate}
              maxDate={maxDate}
              disabledDates={disabledDates}
              highlightedDates={highlightedDates}
              locale={locale}
              firstDayOfWeek={firstDayOfWeek}
              showWeekNumbers={showWeekNumbers}
              showTodayButton={showToday}
              showClearButton={showClear}
              size={size === 'sm' ? 'sm' : size === 'lg' ? 'lg' : 'md'}
            />
          </div>

          {/* Sélecteur d'heure */}
          {showTime && (
            <div className="border-t border-gray-200 p-3 dark:border-gray-700">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-gray-400" />
                <Input
                  type="text"
                  value={timeValue}
                  onChange={handleTimeChange}
                  placeholder={timeFormat === '12h' ? 'HH:MM AM/PM' : 'HH:MM'}
                  className="h-8 w-28 text-sm"
                  disabled={!selectedDate}
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs"
                  onClick={() => {
                    if (selectedDate) {
                      const now = new Date();
                      setTimeValue(format(now, TIME_FORMATS[timeFormat]));
                      const newDate = new Date(selectedDate);
                      newDate.setHours(now.getHours(), now.getMinutes(), 0, 0);
                      setSelectedDate(newDate);
                      onChange?.(newDate);
                    }
                  }}
                >
                  Maintenant
                </Button>
              </div>
            </div>
          )}
        </PopoverContent>
      </Popover>

      {/* Erreur */}
      {error && (
        <p id={errorId} className="mt-1.5 text-xs text-red-500">
          {error}
        </p>
      )}

      {/* Description */}
      {description && !error && (
        <p id={descriptionId} className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
          {description}
        </p>
      )}
    </div>
  );
}

// ============================================
// EXPORTATIONS
// ============================================

export default DatePicker;

/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import { cn } from '@/utils/helpers';
import { Button } from './Button';
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface CalendarProps {
  value?: Date;
  onChange?: (date: Date) => void;
  onSelect?: (date: Date) => void;
  minDate?: Date;
  maxDate?: Date;
  disabledDates?: Date[];
  highlightedDates?: Date[];
  locale?: string;
  firstDayOfWeek?: 0 | 1 | 2 | 3 | 4 | 5 | 6;
  showWeekNumbers?: boolean;
  showOutsideDays?: boolean;
  showTodayButton?: boolean;
  showClearButton?: boolean;
  disablePastDates?: boolean;
  disableFutureDates?: boolean;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'outline' | 'ghost';
}

// ============================================
// CONSTANTES
// ============================================

const DAYS_IN_WEEK = 7;
const MONTHS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
];
const DAYS_SHORT = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'];
const DAYS_LONG = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'];

// ============================================
// COMPOSANT
// ============================================

export function Calendar({
  value,
  onChange,
  onSelect,
  minDate,
  maxDate,
  disabledDates = [],
  highlightedDates = [],
  locale = 'fr',
  firstDayOfWeek = 1,
  showWeekNumbers = false,
  showOutsideDays = true,
  showTodayButton = true,
  showClearButton = true,
  disablePastDates = false,
  disableFutureDates = false,
  className,
  size = 'md',
  variant = 'default',
}: CalendarProps) {
  // ============================================
  // ÉTATS
  // ============================================
  const [currentDate, setCurrentDate] = React.useState(value || new Date());
  const [selectedDate, setSelectedDate] = React.useState<Date | undefined>(value);
  const [viewDate, setViewDate] = React.useState(currentDate);
  const [viewMode, setViewMode] = React.useState<'day' | 'month' | 'year'>('day');

  // ============================================
  // RÉFÉRENCES
  // ============================================
  const calendarRef = React.useRef<HTMLDivElement>(null);

  // ============================================
  // FONCTIONS
  // ============================================

  const getDaysInMonth = (date: Date): number => {
    return new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
  };

  const getFirstDayOfMonth = (date: Date): number => {
    const firstDay = new Date(date.getFullYear(), date.getMonth(), 1).getDay();
    return (firstDay - firstDayOfWeek + 7) % 7;
  };

  const getMonthDays = (date: Date): (Date | null)[] => {
    const daysInMonth = getDaysInMonth(date);
    const firstDay = getFirstDayOfMonth(date);
    const days: (Date | null)[] = [];

    // Jours du mois précédent
    const prevMonth = new Date(date.getFullYear(), date.getMonth() - 1);
    const daysInPrevMonth = getDaysInMonth(prevMonth);

    for (let i = firstDay - 1; i >= 0; i--) {
      const day = daysInPrevMonth - i;
      days.push(new Date(prevMonth.getFullYear(), prevMonth.getMonth(), day));
    }

    // Jours du mois courant
    for (let i = 1; i <= daysInMonth; i++) {
      days.push(new Date(date.getFullYear(), date.getMonth(), i));
    }

    // Jours du mois suivant
    const nextMonth = new Date(date.getFullYear(), date.getMonth() + 1);
    const remainingDays = DAYS_IN_WEEK - (days.length % DAYS_IN_WEEK);

    if (remainingDays < DAYS_IN_WEEK) {
      for (let i = 1; i <= remainingDays; i++) {
        days.push(new Date(nextMonth.getFullYear(), nextMonth.getMonth(), i));
      }
    }

    return days;
  };

  const isDateDisabled = (date: Date): boolean => {
    if (disablePastDates && date < new Date(new Date().setHours(0, 0, 0, 0))) {
      return true;
    }
    if (disableFutureDates && date > new Date(new Date().setHours(0, 0, 0, 0))) {
      return true;
    }
    if (minDate && date < minDate) return true;
    if (maxDate && date > maxDate) return true;
    if (disabledDates.some(d => isSameDay(d, date))) return true;
    return false;
  };

  const isSameDay = (date1: Date, date2: Date): boolean => {
    return (
      date1.getFullYear() === date2.getFullYear() &&
      date1.getMonth() === date2.getMonth() &&
      date1.getDate() === date2.getDate()
    );
  };

  const isSameMonth = (date1: Date, date2: Date): boolean => {
    return (
      date1.getFullYear() === date2.getFullYear() &&
      date1.getMonth() === date2.getMonth()
    );
  };

  const isToday = (date: Date): boolean => {
    return isSameDay(date, new Date());
  };

  const isSelected = (date: Date): boolean => {
    return selectedDate ? isSameDay(date, selectedDate) : false;
  };

  const isHighlighted = (date: Date): boolean => {
    return highlightedDates.some(d => isSameDay(d, date));
  };

  const handleDateSelect = (date: Date) => {
    if (isDateDisabled(date)) return;
    setSelectedDate(date);
    onChange?.(date);
    onSelect?.(date);
  };

  const handleMonthChange = (offset: number) => {
    const newDate = new Date(viewDate);
    newDate.setMonth(viewDate.getMonth() + offset);
    setViewDate(newDate);
  };

  const handleYearChange = (offset: number) => {
    const newDate = new Date(viewDate);
    newDate.setFullYear(viewDate.getFullYear() + offset);
    setViewDate(newDate);
  };

  const handleToday = () => {
    const today = new Date();
    setViewDate(today);
    setSelectedDate(today);
    onChange?.(today);
    onSelect?.(today);
  };

  const handleClear = () => {
    setSelectedDate(undefined);
    onChange?.(undefined as any);
    onSelect?.(undefined as any);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!selectedDate) return;

    const newDate = new Date(selectedDate);
    let handled = true;

    switch (e.key) {
      case 'ArrowLeft':
        newDate.setDate(newDate.getDate() - 1);
        break;
      case 'ArrowRight':
        newDate.setDate(newDate.getDate() + 1);
        break;
      case 'ArrowUp':
        newDate.setDate(newDate.getDate() - 7);
        break;
      case 'ArrowDown':
        newDate.setDate(newDate.getDate() + 7);
        break;
      case 'Home':
        newDate.setDate(1);
        break;
      case 'End':
        newDate.setDate(getDaysInMonth(newDate));
        break;
      default:
        handled = false;
    }

    if (handled && !isDateDisabled(newDate)) {
      e.preventDefault();
      setSelectedDate(newDate);
      setViewDate(newDate);
      onChange?.(newDate);
      onSelect?.(newDate);
    }
  };

  // ============================================
  // EFFETS
  // ============================================

  React.useEffect(() => {
    if (value) {
      setSelectedDate(value);
      setViewDate(value);
    }
  }, [value]);

  // ============================================
  // RENDU
  // ============================================

  const days = getMonthDays(viewDate);
  const weeks: (Date | null)[][] = [];
  for (let i = 0; i < days.length; i += DAYS_IN_WEEK) {
    weeks.push(days.slice(i, i + DAYS_IN_WEEK));
  }

  const sizeClasses = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg',
  };

  return (
    <div
      ref={calendarRef}
      className={cn(
        'w-full max-w-sm rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900',
        sizeClasses[size],
        className
      )}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="application"
      aria-label="Calendrier"
    >
      {/* En-tête */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => handleYearChange(-1)}
            aria-label="Année précédente"
          >
            <ChevronsLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => handleMonthChange(-1)}
            aria-label="Mois précédent"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-semibold">
            {MONTHS[viewDate.getMonth()]} {viewDate.getFullYear()}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => handleMonthChange(1)}
            aria-label="Mois suivant"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => handleYearChange(1)}
            aria-label="Année suivante"
          >
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Jours de la semaine */}
      <div className="grid grid-cols-7 mb-2">
        {DAYS_SHORT.map((day, index) => {
          const dayIndex = (index + firstDayOfWeek) % 7;
          return (
            <div
              key={dayIndex}
              className="flex h-8 items-center justify-center text-xs font-medium text-gray-500 dark:text-gray-400"
            >
              {day}
            </div>
          );
        })}
      </div>

      {/* Grille des jours */}
      <div className="grid grid-cols-7 gap-0.5">
        {weeks.map((week, weekIndex) => (
          <React.Fragment key={weekIndex}>
            {showWeekNumbers && (
              <div className="flex h-8 items-center justify-center text-xs text-gray-400">
                {weekIndex + 1}
              </div>
            )}
            {week.map((day, dayIndex) => {
              if (!day) {
                return <div key={dayIndex} className="h-8" />;
              }

              const isCurrentMonth = isSameMonth(day, viewDate);
              const isDisabled = isDateDisabled(day);
              const isSelectedDay = isSelected(day);
              const isTodayDay = isToday(day);
              const isHighlightedDay = isHighlighted(day);

              return (
                <button
                  key={dayIndex}
                  className={cn(
                    'flex h-8 w-full items-center justify-center rounded-md text-sm transition-colors',
                    'hover:bg-gray-100 dark:hover:bg-gray-800',
                    !isCurrentMonth && 'text-gray-400 dark:text-gray-600',
                    isDisabled && 'cursor-not-allowed opacity-50 hover:bg-transparent',
                    isSelectedDay && 'bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-700',
                    isTodayDay && !isSelectedDay && 'border border-blue-600 dark:border-blue-400',
                    isHighlightedDay && !isSelectedDay && 'bg-yellow-50 dark:bg-yellow-900/20',
                    'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2'
                  )}
                  onClick={() => handleDateSelect(day)}
                  disabled={isDisabled}
                  aria-label={day.toLocaleDateString(locale)}
                  aria-selected={isSelectedDay}
                  role="gridcell"
                >
                  {day.getDate()}
                </button>
              );
            })}
          </React.Fragment>
        ))}
      </div>

      {/* Pied de page */}
      <div className="mt-4 flex items-center justify-between gap-2">
        {showTodayButton && (
          <Button
            variant="outline"
            size="sm"
            className="h-8 px-3 text-xs"
            onClick={handleToday}
          >
            Aujourd'hui
          </Button>
        )}
        {showClearButton && selectedDate && (
          <Button
            variant="ghost"
            size="sm"
            className="h-8 px-3 text-xs text-red-600 hover:text-red-700"
            onClick={handleClear}
          >
            Effacer
          </Button>
        )}
      </div>
    </div>
  );
}

// ============================================
// EXPORTATIONS
// ============================================

export default Calendar;

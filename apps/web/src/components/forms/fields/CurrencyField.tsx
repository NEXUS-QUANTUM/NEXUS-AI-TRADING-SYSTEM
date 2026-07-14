// apps/web/src/components/forms/fields/CurrencyField.tsx
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
  CurrencyDollarIcon,
  BanknotesIcon,
  CreditCardIcon,
  WalletIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  XMarkIcon,
  CheckIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  CalculatorIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  PlusIcon,
  MinusIcon,
  PercentIcon,
  GlobeAltIcon,
} from '@heroicons/react/24/outline';
import { Input } from '@/components/common/Input';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';
import { Popover } from '@/components/common/Popover';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type CurrencyCode = 
  | 'USD' | 'EUR' | 'GBP' | 'JPY' | 'CHF' | 'CAD' | 'AUD' | 'NZD'
  | 'CNY' | 'HKD' | 'SGD' | 'KRW' | 'INR' | 'BRL' | 'ZAR'
  | 'BTC' | 'ETH' | 'USDT' | 'USDC' | 'DAI'
  | 'XAU' | 'XAG'
  | string;

export type CurrencyDisplay = 'symbol' | 'code' | 'name' | 'both';
export type CurrencyFormat = 'decimal' | 'compact' | 'scientific' | 'engineering';
export type CurrencyRounding = 'none' | 'floor' | 'ceil' | 'round' | 'truncate';

export interface CurrencyInfo {
  code: CurrencyCode;
  symbol: string;
  name: string;
  decimals: number;
  locale: string;
  flag?: string;
  icon?: React.ReactNode;
  isCrypto?: boolean;
  isFiat?: boolean;
}

export interface CurrencyFieldProps {
  // --- Contrôle ---
  /** Valeur du champ */
  value?: number | string;
  /** Valeur par défaut */
  defaultValue?: number | string;
  /** Callback de changement */
  onChange?: (value: number | string | null) => void;
  /** Callback de blur */
  onBlur?: (value: number | string | null) => void;
  /** Callback de focus */
  onFocus?: (value: number | string | null) => void;
  /** Callback de validation */
  onValidate?: (valid: boolean, value: number | string | null) => void;

  // --- Devise ---
  /** Code de la devise */
  currency?: CurrencyCode;
  /** Devises disponibles */
  availableCurrencies?: CurrencyCode[];
  /** Devise par défaut */
  defaultCurrency?: CurrencyCode;
  /** Callback de changement de devise */
  onCurrencyChange?: (currency: CurrencyCode) => void;

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
  /** Afficher le symbole de la devise */
  showSymbol?: boolean;
  /** Afficher le code de la devise */
  showCode?: boolean;
  /** Afficher le sélecteur de devise */
  showCurrencySelector?: boolean;
  /** Afficher les boutons de présets */
  showPresets?: boolean;
  /** Afficher la calculatrice */
  showCalculator?: boolean;
  /** Afficher les notifications de conversion */
  showConversion?: boolean;
  /** Position du symbole */
  symbolPosition?: 'prefix' | 'suffix';
  /** Format d'affichage */
  displayFormat?: CurrencyDisplay;
  /** Format numérique */
  numberFormat?: CurrencyFormat;
  /** Arrondi */
  rounding?: CurrencyRounding;
  /** Nombre de décimales */
  decimals?: number;
  /** Séparateur de milliers */
  thousandsSeparator?: string;
  /** Séparateur décimal */
  decimalSeparator?: string;

  // --- Comportement ---
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Désactiver les valeurs négatives */
  allowNegative?: boolean;
  /** Désactiver les valeurs nulles */
  allowNull?: boolean;
  /** Valeur minimale */
  min?: number;
  /** Valeur maximale */
  max?: number;
  /** Pas d'incrémentation */
  step?: number;
  /** Afficher les boutons d'incrémentation */
  showStepper?: boolean;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Désactiver le formatage automatique */
  disableAutoFormat?: boolean;
  /** Désactiver la conversion de devise */
  disableConversion?: boolean;

  // --- Présets ---
  /** Valeurs présélectionnées */
  presets?: number[];
  /** Libellés des présets */
  presetLabels?: string[];
  /** Pourcentages présélectionnés */
  percentagePresets?: number[];

  // --- Conversion ---
  /** Taux de conversion */
  conversionRate?: number;
  /** Devise cible pour la conversion */
  targetCurrency?: CurrencyCode;
  /** Afficher la valeur convertie */
  showConvertedValue?: boolean;
  /** Format de la valeur convertie */
  convertedFormat?: CurrencyFormat;

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
  customFormat?: (value: number, currency: CurrencyCode) => string;
  /** Fonction de parsing personnalisée */
  customParse?: (value: string, currency: CurrencyCode) => number | null;
  /** Fonction de validation personnalisée */
  customValidate?: (value: number | string | null) => boolean | string;
  /** Ref */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES - DEVISES
// ============================================================================

export const CURRENCIES: Record<CurrencyCode, CurrencyInfo> = {
  // Devises majeures
  USD: { code: 'USD', symbol: '$', name: 'Dollar US', decimals: 2, locale: 'en-US', flag: '🇺🇸' },
  EUR: { code: 'EUR', symbol: '€', name: 'Euro', decimals: 2, locale: 'fr-FR', flag: '🇪🇺' },
  GBP: { code: 'GBP', symbol: '£', name: 'Livre Sterling', decimals: 2, locale: 'en-GB', flag: '🇬🇧' },
  JPY: { code: 'JPY', symbol: '¥', name: 'Yen Japonais', decimals: 0, locale: 'ja-JP', flag: '🇯🇵' },
  CHF: { code: 'CHF', symbol: 'Fr.', name: 'Franc Suisse', decimals: 2, locale: 'de-CH', flag: '🇨🇭' },
  CAD: { code: 'CAD', symbol: 'C$', name: 'Dollar Canadien', decimals: 2, locale: 'en-CA', flag: '🇨🇦' },
  AUD: { code: 'AUD', symbol: 'A$', name: 'Dollar Australien', decimals: 2, locale: 'en-AU', flag: '🇦🇺' },
  NZD: { code: 'NZD', symbol: 'NZ$', name: 'Dollar Néo-Zélandais', decimals: 2, locale: 'en-NZ', flag: '🇳🇿' },
  CNY: { code: 'CNY', symbol: '¥', name: 'Yuan Chinois', decimals: 2, locale: 'zh-CN', flag: '🇨🇳' },
  HKD: { code: 'HKD', symbol: 'HK$', name: 'Dollar de Hong Kong', decimals: 2, locale: 'zh-HK', flag: '🇭🇰' },
  SGD: { code: 'SGD', symbol: 'S$', name: 'Dollar de Singapour', decimals: 2, locale: 'en-SG', flag: '🇸🇬' },
  KRW: { code: 'KRW', symbol: '₩', name: 'Won Coréen', decimals: 0, locale: 'ko-KR', flag: '🇰🇷' },
  INR: { code: 'INR', symbol: '₹', name: 'Roupie Indienne', decimals: 2, locale: 'en-IN', flag: '🇮🇳' },
  BRL: { code: 'BRL', symbol: 'R$', name: 'Real Brésilien', decimals: 2, locale: 'pt-BR', flag: '🇧🇷' },
  ZAR: { code: 'ZAR', symbol: 'R', name: 'Rand Sud-Africain', decimals: 2, locale: 'en-ZA', flag: '🇿🇦' },
  
  // Cryptomonnaies
  BTC: { code: 'BTC', symbol: '₿', name: 'Bitcoin', decimals: 8, locale: 'en-US', flag: '₿', isCrypto: true },
  ETH: { code: 'ETH', symbol: 'Ξ', name: 'Ethereum', decimals: 8, locale: 'en-US', flag: 'Ξ', isCrypto: true },
  USDT: { code: 'USDT', symbol: '₮', name: 'Tether', decimals: 2, locale: 'en-US', flag: '₮', isCrypto: true },
  USDC: { code: 'USDC', symbol: '₮', name: 'USD Coin', decimals: 2, locale: 'en-US', flag: '₮', isCrypto: true },
  DAI: { code: 'DAI', symbol: '◈', name: 'Dai', decimals: 2, locale: 'en-US', flag: '◈', isCrypto: true },
  
  // Métaux précieux
  XAU: { code: 'XAU', symbol: 'Au', name: 'Or', decimals: 2, locale: 'en-US', flag: '🥇' },
  XAG: { code: 'XAG', symbol: 'Ag', name: 'Argent', decimals: 2, locale: 'en-US', flag: '🥈' },
};

const DEFAULT_CURRENCY: CurrencyCode = 'USD';
const DEFAULT_DECIMALS = 2;

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const CurrencyField = forwardRef<HTMLInputElement, CurrencyFieldProps>(
  (props, ref) => {
    const {
      // Contrôle
      value: externalValue,
      defaultValue,
      onChange,
      onBlur,
      onFocus,
      onValidate,

      // Devise
      currency: externalCurrency,
      availableCurrencies = ['USD', 'EUR', 'GBP', 'JPY', 'CHF', 'BTC', 'ETH'],
      defaultCurrency = DEFAULT_CURRENCY,
      onCurrencyChange,

      // Apparence
      label,
      placeholder = '0.00',
      description,
      error,
      success,
      info,
      showSymbol = true,
      showCode = false,
      showCurrencySelector = true,
      showPresets = true,
      showCalculator = true,
      showConversion = true,
      symbolPosition = 'prefix',
      displayFormat = 'both',
      numberFormat = 'decimal',
      rounding = 'round',
      decimals: customDecimals,
      thousandsSeparator = ' ',
      decimalSeparator = '.',

      // Comportement
      disabled = false,
      required = false,
      allowNegative = true,
      allowNull = true,
      min = -Infinity,
      max = Infinity,
      step = 1,
      showStepper = false,
      disableRealtimeValidation = false,
      disableAutoFormat = false,
      disableConversion = false,

      // Présets
      presets = [],
      presetLabels = [],
      percentagePresets = [25, 50, 75, 100],

      // Conversion
      conversionRate = 1,
      targetCurrency = 'EUR',
      showConvertedValue = false,
      convertedFormat = 'decimal',

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,
      name,

      // Avancé
      customFormat,
      customParse,
      customValidate,
      inputRef,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const inputRefInternal = useRef<HTMLInputElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const isFocusedRef = useRef(false);
    const prevValueRef = useRef<number | string | null>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState<number | string | null>(
      defaultValue !== undefined ? defaultValue : null
    );
    const [currency, setCurrency] = useState<CurrencyCode>(
      externalCurrency || defaultCurrency
    );
    const [displayValue, setDisplayValue] = useState<string>('');
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');
    const [showCalculator, setShowCalculator] = useState(false);
    const [calculatorInput, setCalculatorInput] = useState('');
    const [convertedValue, setConvertedValue] = useState<string>('');
    const [isConverting, setIsConverting] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const currencyInfo = CURRENCIES[currency] || CURRENCIES[DEFAULT_CURRENCY];
    const decimals = customDecimals !== undefined ? customDecimals : currencyInfo.decimals;
    const numericValue = typeof value === 'number' ? value : parseFloat(String(value)) || 0;

    // ========================================================================
    // FORMATAGE
    // ========================================================================

    const formatCurrency = useCallback((val: number | string | null): string => {
      if (val === null || val === undefined || val === '') return '';

      const num = typeof val === 'string' ? parseFloat(val) : val;
      if (isNaN(num)) return '';

      if (customFormat) {
        return customFormat(num, currency);
      }

      let formatted = '';

      // Formatage numérique
      switch (numberFormat) {
        case 'compact':
          if (Math.abs(num) >= 1e9) {
            formatted = (num / 1e9).toFixed(1) + 'B';
          } else if (Math.abs(num) >= 1e6) {
            formatted = (num / 1e6).toFixed(1) + 'M';
          } else if (Math.abs(num) >= 1e3) {
            formatted = (num / 1e3).toFixed(1) + 'k';
          } else {
            formatted = num.toFixed(decimals);
          }
          break;
        case 'scientific':
          formatted = num.toExponential(decimals);
          break;
        case 'engineering':
          const exp = Math.floor(Math.log10(Math.abs(num)) / 3) * 3;
          const mantissa = num / Math.pow(10, exp);
          formatted = mantissa.toFixed(decimals) + 'e' + (exp >= 0 ? '+' : '') + exp;
          break;
        default:
          // Arrondi
          let rounded = num;
          switch (rounding) {
            case 'floor':
              rounded = Math.floor(num * Math.pow(10, decimals)) / Math.pow(10, decimals);
              break;
            case 'ceil':
              rounded = Math.ceil(num * Math.pow(10, decimals)) / Math.pow(10, decimals);
              break;
            case 'truncate':
              rounded = Math.trunc(num * Math.pow(10, decimals)) / Math.pow(10, decimals);
              break;
            default:
              rounded = num;
          }
          formatted = rounded.toFixed(decimals);
          // Remplacer les séparateurs
          if (thousandsSeparator !== ',') {
            const parts = formatted.split('.');
            parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, thousandsSeparator);
            formatted = parts.join(decimalSeparator);
          }
      }

      // Ajouter le symbole
      const symbol = showSymbol ? currencyInfo.symbol : '';
      const code = showCode ? currencyInfo.code : '';

      if (symbolPosition === 'prefix') {
        return `${symbol}${symbol && code ? ' ' : ''}${code}${code ? ' ' : ''}${formatted}`;
      } else {
        return `${formatted} ${symbol}${symbol && code ? ' ' : ''}${code}`.trim();
      }
    }, [
      currency,
      currencyInfo,
      decimals,
      numberFormat,
      rounding,
      thousandsSeparator,
      decimalSeparator,
      showSymbol,
      showCode,
      symbolPosition,
      customFormat,
    ]);

    const parseCurrency = useCallback((text: string): number | null => {
      if (!text || text.trim() === '') return null;

      if (customParse) {
        return customParse(text, currency);
      }

      // Nettoyer le texte
      let cleaned = text
        .replace(new RegExp(`[${currencyInfo.symbol}]`, 'g'), '')
        .replace(new RegExp(`[${Object.values(CURRENCIES).map(c => c.symbol).join('')}]`, 'g'), '')
        .replace(/[^\d.,\-+eE]/g, '')
        .trim();

      // Remplacer les séparateurs
      if (decimalSeparator !== '.') {
        cleaned = cleaned.replace(new RegExp(`\\${thousandsSeparator}`, 'g'), '')
                         .replace(new RegExp(`\\${decimalSeparator}`), '.');
      } else {
        cleaned = cleaned.replace(/,/g, '');
      }

      // Gérer les pourcentages
      if (cleaned.endsWith('%')) {
        const num = parseFloat(cleaned.slice(0, -1));
        return isNaN(num) ? null : num / 100;
      }

      const num = parseFloat(cleaned);
      return isNaN(num) ? null : num;
    }, [currency, currencyInfo, customParse, thousandsSeparator, decimalSeparator]);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateValue = useCallback((val: number | string | null): { valid: boolean; message: string } => {
      if (customValidate) {
        const result = customValidate(val);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (val === null || val === undefined || val === '') {
        if (required) {
          return { valid: false, message: 'Ce champ est requis' };
        }
        return { valid: true, message: '' };
      }

      const num = typeof val === 'string' ? parseFloat(val) : val;
      if (isNaN(num)) {
        return { valid: false, message: 'Veuillez entrer un nombre valide' };
      }

      if (!allowNegative && num < 0) {
        return { valid: false, message: 'Les valeurs négatives ne sont pas autorisées' };
      }

      if (num < min) {
        return { valid: false, message: `La valeur minimale est ${formatCurrency(min)}` };
      }

      if (num > max) {
        return { valid: false, message: `La valeur maximale est ${formatCurrency(max)}` };
      }

      return { valid: true, message: '' };
    }, [required, allowNegative, min, max, formatCurrency, customValidate]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((newValue: number | string | null) => {
      const parsed = typeof newValue === 'string' ? parseCurrency(newValue) : newValue;
      const finalValue = parsed !== null && !isNaN(parsed) ? parsed : (allowNull ? null : 0);

      // Validation
      const validation = validateValue(finalValue);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, finalValue);
      }

      // Mise à jour
      if (isControlled) {
        if (onChange) onChange(finalValue);
      } else {
        setInternalValue(finalValue);
        if (onChange) onChange(finalValue);
      }

      // Formatage pour affichage
      if (!disableAutoFormat) {
        const formatted = formatCurrency(finalValue);
        setDisplayValue(formatted);
      }

      if (debug) {
        console.log('CurrencyField update:', { newValue, parsed, finalValue, isValid: validation.valid });
      }
    }, [
      allowNull,
      formatCurrency,
      parseCurrency,
      validateValue,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      disableAutoFormat,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      const rawValue = e.target.value;
      setDisplayValue(rawValue);

      if (!disableRealtimeValidation) {
        const parsed = parseCurrency(rawValue);
        const validation = validateValue(parsed);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        if (onValidate) onValidate(validation.valid, parsed);
      }

      if (!isFocusedRef.current) {
        // Si pas focus, formater automatiquement
        const parsed = parseCurrency(rawValue);
        updateValue(parsed);
      }
    }, [disableRealtimeValidation, parseCurrency, validateValue, onValidate, updateValue, isFocusedRef]);

    const handleFocus = useCallback((e: React.FocusEvent<HTMLInputElement>) => {
      setIsFocused(true);
      isFocusedRef.current = true;
      
      // Sélectionner tout le texte
      e.target.select();
      
      if (onFocus) onFocus(value);
    }, [onFocus, value]);

    const handleBlur = useCallback((e: React.FocusEvent<HTMLInputElement>) => {
      setIsFocused(false);
      isFocusedRef.current = false;

      // Formater la valeur à la perte de focus
      const parsed = parseCurrency(e.target.value);
      const finalValue = parsed !== null && !isNaN(parsed) ? parsed : (allowNull ? null : 0);
      
      if (!disableAutoFormat) {
        const formatted = formatCurrency(finalValue);
        setDisplayValue(formatted);
      }

      // Valider
      const validation = validateValue(finalValue);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);
      if (onValidate) onValidate(validation.valid, finalValue);

      // Mettre à jour
      if (!isControlled) {
        setInternalValue(finalValue);
      }
      if (onChange) onChange(finalValue);
      if (onBlur) onBlur(finalValue);

      if (debug) {
        console.log('CurrencyField blur:', { finalValue, formatted: formatCurrency(finalValue) });
      }
    }, [
      parseCurrency,
      allowNull,
      disableAutoFormat,
      formatCurrency,
      validateValue,
      onValidate,
      isControlled,
      onChange,
      onBlur,
      debug,
    ]);

    // ========================================================================
    // GESTION DES TOUCHES
    // ========================================================================

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        const current = parseCurrency(displayValue) || 0;
        updateValue(current + step);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        const current = parseCurrency(displayValue) || 0;
        updateValue(current - step);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const parsed = parseCurrency(displayValue);
        if (parsed !== null) {
          updateValue(parsed);
        }
        inputRefInternal.current?.blur();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        inputRefInternal.current?.blur();
      }
    }, [displayValue, parseCurrency, updateValue, step]);

    // ========================================================================
    // CHANGEMENT DE DEVISE
    // ========================================================================

    const handleCurrencyChange = useCallback((newCurrency: CurrencyCode) => {
      if (newCurrency === currency) return;

      // Convertir la valeur si un taux est disponible
      if (!disableConversion && conversionRate > 0) {
        const currentValue = parseCurrency(displayValue) || 0;
        const converted = currentValue * conversionRate;
        setCurrency(newCurrency);
        updateValue(converted);
      } else {
        setCurrency(newCurrency);
      }

      if (onCurrencyChange) onCurrencyChange(newCurrency);

      if (debug) {
        console.log('CurrencyField change currency:', { from: currency, to: newCurrency });
      }
    }, [currency, disableConversion, conversionRate, displayValue, parseCurrency, updateValue, onCurrencyChange, debug]);

    // ========================================================================
    // PRÉSÉLECTIONS
    // ========================================================================

    const handlePresetClick = useCallback((preset: number) => {
      updateValue(preset);
      if (debug) console.log('CurrencyField preset:', preset);
    }, [updateValue, debug]);

    const handlePercentagePreset = useCallback((percent: number) => {
      const current = parseCurrency(displayValue) || 0;
      const newValue = (current * percent) / 100;
      updateValue(newValue);
      if (debug) console.log('CurrencyField percentage:', { percent, newValue });
    }, [displayValue, parseCurrency, updateValue, debug]);

    // ========================================================================
    // CALCULATRICE
    // ========================================================================

    const handleCalculatorClick = useCallback(() => {
      setShowCalculator(!showCalculator);
      if (!showCalculator) {
        setCalculatorInput(displayValue);
      }
    }, [showCalculator, displayValue]);

    const handleCalculatorChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      setCalculatorInput(e.target.value);
    }, []);

    const handleCalculatorSubmit = useCallback(() => {
      try {
        // Évaluer l'expression mathématique
        const result = Function('"use strict"; return (' + calculatorInput + ')')();
        if (typeof result === 'number' && !isNaN(result)) {
          updateValue(result);
          setShowCalculator(false);
          toast({
            title: 'Calcul effectué',
            description: `Résultat: ${formatCurrency(result)}`,
            duration: 2000,
          });
        }
      } catch (error) {
        toast({
          title: 'Erreur de calcul',
          description: 'Expression invalide',
          variant: 'destructive',
          duration: 3000,
        });
      }
    }, [calculatorInput, updateValue, formatCurrency, toast]);

    // ========================================================================
    // CONVERSION
    // ========================================================================

    useEffect(() => {
      if (!showConvertedValue || !conversionRate || disableConversion) return;

      const numericVal = parseCurrency(displayValue);
      if (numericVal !== null && !isNaN(numericVal)) {
        const converted = numericVal * conversionRate;
        const targetInfo = CURRENCIES[targetCurrency] || CURRENCIES[DEFAULT_CURRENCY];
        const targetDecimals = targetInfo.decimals || 2;
        
        let formatted = converted.toFixed(targetDecimals);
        if (convertedFormat === 'compact') {
          if (Math.abs(converted) >= 1e9) formatted = (converted / 1e9).toFixed(1) + 'B';
          else if (Math.abs(converted) >= 1e6) formatted = (converted / 1e6).toFixed(1) + 'M';
          else if (Math.abs(converted) >= 1e3) formatted = (converted / 1e3).toFixed(1) + 'k';
        }
        
        setConvertedValue(`${targetInfo.symbol} ${formatted} ${targetInfo.code}`);
      } else {
        setConvertedValue('');
      }
    }, [
      displayValue,
      showConvertedValue,
      conversionRate,
      targetCurrency,
      disableConversion,
      parseCurrency,
      convertedFormat,
    ]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined && externalValue !== prevValueRef.current) {
        prevValueRef.current = externalValue;
        if (!disableAutoFormat) {
          const formatted = formatCurrency(externalValue);
          setDisplayValue(formatted);
        }
      }
    }, [externalValue, formatCurrency, disableAutoFormat]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue !== undefined && !isControlled) {
        const formatted = formatCurrency(defaultValue);
        setDisplayValue(formatted);
      }
    }, [defaultValue, formatCurrency, isControlled]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => inputRefInternal.current?.focus(),
      blur: () => inputRefInternal.current?.blur(),
      select: () => inputRefInternal.current?.select(),
      getValue: () => value,
      getCurrency: () => currency,
      setValue: (val: number | string | null) => updateValue(val),
      setCurrency: (curr: CurrencyCode) => handleCurrencyChange(curr),
      validate: () => {
        const validation = validateValue(value);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU
    // ========================================================================

    const currencyOptions = availableCurrencies.map((code) => ({
      value: code,
      label: CURRENCIES[code]?.name || code,
      symbol: CURRENCIES[code]?.symbol || code,
      flag: CURRENCIES[code]?.flag || '',
    }));

    const currentCurrencyInfo = CURRENCIES[currency] || CURRENCIES[DEFAULT_CURRENCY];
    const currencyDisplay = showCode 
      ? (showSymbol ? `${currentCurrencyInfo.symbol} ${currentCurrencyInfo.code}` : currentCurrencyInfo.code)
      : (showSymbol ? currentCurrencyInfo.symbol : '');

    const hasError = !!error || !isValid || (required && !value);

    return (
      <div 
        ref={containerRef} 
        className="relative space-y-1.5"
        id={id}
      >
        {/* Label */}
        {label && (
          <div className="flex items-center justify-between">
            <Label 
              htmlFor={id || name} 
              className="text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              {label}
              {required && <span className="ml-1 text-red-500">*</span>}
            </Label>
            
            {/* Sélecteur de devise */}
            {showCurrencySelector && (
              <div className="flex items-center gap-1">
                <Popover
                  trigger={
                    <button
                      type="button"
                      className="flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                      disabled={disabled}
                    >
                      <span>{currentCurrencyInfo.flag || currentCurrencyInfo.symbol}</span>
                      <span>{currentCurrencyInfo.code}</span>
                      <ChevronDownIcon className="h-3 w-3 text-gray-400" />
                    </button>
                  }
                  placement="bottom-end"
                  size="sm"
                >
                  <div className="max-h-64 overflow-y-auto p-1">
                    {currencyOptions.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        className={cn(
                          'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
                          currency === opt.value
                            ? 'bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400'
                            : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                        )}
                        onClick={() => handleCurrencyChange(opt.value as CurrencyCode)}
                      >
                        <span>{opt.flag || opt.symbol}</span>
                        <span className="flex-1 text-left">{opt.label}</span>
                        <span className="text-xs text-gray-400">{opt.value}</span>
                        {currency === opt.value && (
                          <CheckIcon className="h-4 w-4 text-brand-500" />
                        )}
                      </button>
                    ))}
                  </div>
                </Popover>
              </div>
            )}
          </div>
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
            {/* Préfixe */}
            {symbolPosition === 'prefix' && showSymbol && (
              <span className="flex-shrink-0 pl-3 text-gray-500 dark:text-gray-400 font-medium">
                {currencyDisplay}
              </span>
            )}

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
              inputMode="decimal"
              className={cn(
                'w-full bg-transparent px-3 py-2 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 outline-none',
                disabled && 'cursor-not-allowed',
                symbolPosition === 'prefix' && showSymbol && 'pl-2',
                symbolPosition === 'suffix' && showSymbol && 'pr-2'
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

            {/* Suffixe */}
            {symbolPosition === 'suffix' && showSymbol && (
              <span className="flex-shrink-0 pr-3 text-gray-500 dark:text-gray-400 font-medium">
                {currencyDisplay}
              </span>
            )}

            {/* Stepper */}
            {showStepper && !disabled && (
              <div className="flex flex-col border-l border-gray-200 dark:border-gray-700">
                <button
                  type="button"
                  className="flex h-1/2 w-6 items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                  onClick={() => {
                    const current = parseCurrency(displayValue) || 0;
                    updateValue(current + step);
                  }}
                  disabled={disabled}
                >
                  <ChevronUpIcon className="h-3 w-3" />
                </button>
                <button
                  type="button"
                  className="flex h-1/2 w-6 items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors border-t border-gray-200 dark:border-gray-700"
                  onClick={() => {
                    const current = parseCurrency(displayValue) || 0;
                    updateValue(current - step);
                  }}
                  disabled={disabled}
                >
                  <ChevronDownIcon className="h-3 w-3" />
                </button>
              </div>
            )}
          </div>

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

        {/* Présélections */}
        {showPresets && !disabled && (presets.length > 0 || percentagePresets.length > 0) && (
          <div className="flex flex-wrap gap-1 pt-1">
            {presets.map((preset, index) => (
              <button
                key={index}
                type="button"
                className="rounded-lg border border-gray-200 dark:border-gray-700 px-2 py-0.5 text-xs transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
                onClick={() => handlePresetClick(preset)}
              >
                {formatCurrency(preset)}
              </button>
            ))}
            {percentagePresets.map((percent) => (
              <button
                key={`pct-${percent}`}
                type="button"
                className="rounded-lg border border-gray-200 dark:border-gray-700 px-2 py-0.5 text-xs transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
                onClick={() => handlePercentagePreset(percent)}
              >
                {percent}%
              </button>
            ))}
          </div>
        )}

        {/* Conversion */}
        {showConvertedValue && convertedValue && !isConverting && (
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 pt-1">
            <ArrowTrendingUpIcon className="h-3 w-3" />
            <span>{convertedValue}</span>
            <Badge variant="outline" size="xs">Taux: {conversionRate}</Badge>
          </div>
        )}

        {/* Calculatrice */}
        {showCalculator && !disabled && (
          <Popover
            open={showCalculator}
            onOpenChange={setShowCalculator}
            trigger={
              <button
                type="button"
                className="absolute right-10 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                onClick={handleCalculatorClick}
              >
                <CalculatorIcon className="h-4 w-4" />
              </button>
            }
            placement="bottom-end"
            size="sm"
          >
            <div className="p-3 space-y-2 min-w-[200px]">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Calculatrice</span>
                <button
                  type="button"
                  onClick={() => setShowCalculator(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </div>
              <input
                type="text"
                className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-2 py-1.5 text-sm font-mono focus:border-brand-500 focus:outline-none"
                value={calculatorInput}
                onChange={handleCalculatorChange}
                placeholder="Ex: (100+50)*2"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCalculatorSubmit();
                }}
                autoFocus
              />
              <div className="grid grid-cols-4 gap-1">
                {['7','8','9','+','4','5','6','-','1','2','3','*','0','.','/','='].map((btn) => (
                  <button
                    key={btn}
                    type="button"
                    className={cn(
                      'rounded px-2 py-1 text-sm transition-colors',
                      btn === '=' 
                        ? 'col-span-2 bg-brand-500 text-white hover:bg-brand-600'
                        : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                    )}
                    onClick={() => {
                      if (btn === '=') {
                        handleCalculatorSubmit();
                      } else {
                        setCalculatorInput((prev) => prev + btn);
                      }
                    }}
                  >
                    {btn}
                  </button>
                ))}
              </div>
              <div className="flex gap-1">
                <button
                  type="button"
                  className="flex-1 rounded-lg border border-gray-200 dark:border-gray-700 px-2 py-1 text-xs hover:bg-gray-100 dark:hover:bg-gray-800"
                  onClick={() => setCalculatorInput('')}
                >
                  Effacer
                </button>
                <button
                  type="button"
                  className="flex-1 rounded-lg border border-gray-200 dark:border-gray-700 px-2 py-1 text-xs hover:bg-gray-100 dark:hover:bg-gray-800"
                  onClick={() => setCalculatorInput(displayValue)}
                >
                  Restaurer
                </button>
              </div>
            </div>
          </Popover>
        )}
      </div>
    );
  }
);

CurrencyField.displayName = 'CurrencyField';

// ============================================================================
// EXPORTS
// ============================================================================

export default CurrencyField;

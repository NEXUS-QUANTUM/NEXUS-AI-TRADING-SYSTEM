// apps/web/src/components/forms/fields/UrlField.tsx
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
  LinkIcon,
  GlobeAltIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
  CheckIcon,
  ArrowPathIcon,
  ClipboardIcon,
  ShareIcon,
  EyeIcon,
  EyeSlashIcon,
  ArrowTopRightOnSquareIcon,
  DocumentDuplicateIcon,
  MagnifyingGlassIcon,
  ShieldCheckIcon,
  ExclamationCircleIcon,
  GlobeEuropeAfricaIcon,
  GlobeAsiaAustraliaIcon,
  GlobeAmericasIcon,
  WifiIcon,
  SignalIcon,
  LockClosedIcon,
  LockOpenIcon,
  LinkSlashIcon,
  PlusIcon,
  MinusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
} from '@heroicons/react/24/solid';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';
import { Popover } from '@/components/common/Popover';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type UrlProtocol = 'http' | 'https' | 'ftp' | 'ftps' | 'sftp' | 'ws' | 'wss' | 'mailto' | 'tel' | 'sms' | 'custom';
export type UrlValidationLevel = 'basic' | 'standard' | 'strict' | 'custom';
export type UrlStatus = 'idle' | 'valid' | 'invalid' | 'checking' | 'error';

export interface UrlPreview {
  /** Titre de la page */
  title?: string;
  /** Description */
  description?: string;
  /** Favicon */
  favicon?: string;
  /** Image de prévisualisation */
  image?: string;
  /** Site */
  site?: string;
  /** Type */
  type?: string;
  /** Code HTTP */
  statusCode?: number;
}

export interface UrlFieldProps {
  // --- Contrôle ---
  /** Valeur du champ */
  value?: string | null;
  /** Valeur par défaut */
  defaultValue?: string | null;
  /** Callback de changement */
  onChange?: (value: string | null) => void;
  /** Callback de blur */
  onBlur?: () => void;
  /** Callback de focus */
  onFocus?: () => void;
  /** Callback de validation */
  onValidate?: (valid: boolean, value: string | null) => void;

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
  /** Afficher l'icône de validation */
  showValidationIcon?: boolean;
  /** Afficher la prévisualisation */
  showPreview?: boolean;
  /** Afficher le bouton d'ouverture */
  showOpenButton?: boolean;
  /** Afficher le bouton de copie */
  showCopyButton?: boolean;
  /** Afficher le favicon */
  showFavicon?: boolean;
  /** Afficher le protocole */
  showProtocol?: boolean;

  // --- Comportement ---
  /** Protocoles autorisés */
  allowedProtocols?: UrlProtocol[];
  /** Protocoles bloqués */
  blockedProtocols?: UrlProtocol[];
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Validation personnalisée */
  validateUrl?: (url: string) => boolean | string;
  /** Niveau de validation */
  validationLevel?: UrlValidationLevel;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Désactiver la vérification de disponibilité */
  disableAvailabilityCheck?: boolean;
  /** Désactiver le trim */
  disableTrim?: boolean;
  /** Require HTTPS */
  requireHttps?: boolean;

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
  customFormat?: (url: string) => string;
  /** Fonction de parsing personnalisée */
  customParse?: (value: string) => string | null;
  /** Fonction de prévisualisation personnalisée */
  customPreview?: (url: string) => Promise<UrlPreview>;
  /** Ref */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const PROTOCOLS: Record<UrlProtocol, { label: string; prefix: string; defaultPort: number }> = {
  http: { label: 'HTTP', prefix: 'http://', defaultPort: 80 },
  https: { label: 'HTTPS', prefix: 'https://', defaultPort: 443 },
  ftp: { label: 'FTP', prefix: 'ftp://', defaultPort: 21 },
  ftps: { label: 'FTPS', prefix: 'ftps://', defaultPort: 990 },
  sftp: { label: 'SFTP', prefix: 'sftp://', defaultPort: 22 },
  ws: { label: 'WS', prefix: 'ws://', defaultPort: 80 },
  wss: { label: 'WSS', prefix: 'wss://', defaultPort: 443 },
  mailto: { label: 'Mailto', prefix: 'mailto:', defaultPort: 0 },
  tel: { label: 'Tel', prefix: 'tel:', defaultPort: 0 },
  sms: { label: 'SMS', prefix: 'sms:', defaultPort: 0 },
  custom: { label: 'Custom', prefix: '', defaultPort: 0 },
};

const DEFAULT_ALLOWED_PROTOCOLS: UrlProtocol[] = ['https', 'http'];
const DEFAULT_PROTOCOL = 'https';

const URL_REGEX = /^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$/i;
const STRICT_URL_REGEX = /^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$/i;
const IP_REGEX = /^(https?:\/\/)?(\d{1,3}\.){3}\d{1,3}(:\d+)?(\/.*)?$/;

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const UrlField = forwardRef<HTMLInputElement, UrlFieldProps>(
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
      placeholder = 'https://exemple.com',
      description,
      error,
      success,
      info,
      showValidationIcon = true,
      showPreview = true,
      showOpenButton = true,
      showCopyButton = true,
      showFavicon = true,
      showProtocol = true,

      // Comportement
      allowedProtocols = DEFAULT_ALLOWED_PROTOCOLS,
      blockedProtocols = [],
      disabled = false,
      required = false,
      validateUrl: customValidateUrl,
      validationLevel = 'standard',
      disableRealtimeValidation = false,
      disableAvailabilityCheck = false,
      disableTrim = false,
      requireHttps = false,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,
      name,

      // Avancé
      customFormat,
      customParse,
      customPreview,
      inputRef,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const inputRefInternal = useRef<HTMLInputElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const prevValueRef = useRef<string | null>(null);
    const previewTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState<string | null>(
      defaultValue || null
    );
    const [displayValue, setDisplayValue] = useState<string>('');
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');
    const [status, setStatus] = useState<UrlStatus>('idle');
    const [preview, setPreview] = useState<UrlPreview | null>(null);
    const [showPreviewPopover, setShowPreviewPopover] = useState(false);
    const [selectedProtocol, setSelectedProtocol] = useState<UrlProtocol>(DEFAULT_PROTOCOL);
    const [isChecking, setIsChecking] = useState(false);
    const [availabilityStatus, setAvailabilityStatus] = useState<'unknown' | 'available' | 'unavailable'>('unknown');

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const hasValue = value && value.trim().length > 0;
    const displayUrl = hasValue ? value! : '';

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateUrl = useCallback((url: string): { valid: boolean; message: string } => {
      // Validation personnalisée
      if (customValidateUrl) {
        const result = customValidateUrl(url);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      const trimmed = disableTrim ? url : url.trim();
      if (!trimmed) {
        return { valid: false, message: 'L\'URL est requise' };
      }

      // Nettoyer l'URL
      let cleanUrl = trimmed;

      // Ajouter le protocole par défaut si absent
      const hasProtocol = /^[a-z]+:\/\//.test(cleanUrl) || /^(mailto|tel|sms):/.test(cleanUrl);
      if (!hasProtocol) {
        cleanUrl = `${PROTOCOLS[selectedProtocol]?.prefix || 'https://'}${cleanUrl}`;
      }

      // Validation basique
      const basicRegex = /^[a-z]+:\/\/|^(mailto|tel|sms):/;
      if (!basicRegex.test(cleanUrl)) {
        return { valid: false, message: 'Format d\'URL invalide' };
      }

      // Validation standard
      if (validationLevel === 'standard' || validationLevel === 'strict') {
        try {
          const urlObj = new URL(cleanUrl);
          
          // Vérifier le protocole
          const protocol = urlObj.protocol.replace(':', '') as UrlProtocol;
          if (allowedProtocols.length > 0 && !allowedProtocols.includes(protocol)) {
            return { valid: false, message: `Protocole non autorisé. Protocoles autorisés: ${allowedProtocols.join(', ')}` };
          }
          if (blockedProtocols.length > 0 && blockedProtocols.includes(protocol)) {
            return { valid: false, message: `Protocole bloqué: ${protocol}` };
          }

          // Vérifier HTTPS
          if (requireHttps && protocol !== 'https') {
            return { valid: false, message: 'HTTPS est requis' };
          }

          // Vérifier le nom de domaine
          if (urlObj.hostname) {
            const hostname = urlObj.hostname;
            
            // Vérifier l'IP
            if (IP_REGEX.test(cleanUrl)) {
              return { valid: true, message: '' };
            }

            // Vérifier le domaine
            const domainRegex = /^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$/;
            const parts = hostname.split('.');
            if (parts.length < 2) {
              return { valid: false, message: 'Domaine invalide' };
            }
            
            const tld = parts[parts.length - 1];
            if (tld.length < 2) {
              return { valid: false, message: 'Extension de domaine invalide' };
            }
          }

          // Vérifier le chemin
          if (urlObj.pathname.includes('..')) {
            return { valid: false, message: 'Chemin d\'URL invalide' };
          }

        } catch (error) {
          return { valid: false, message: 'URL invalide' };
        }
      }

      // Validation stricte
      if (validationLevel === 'strict') {
        try {
          const urlObj = new URL(cleanUrl);
          
          // Vérifier les caractères spéciaux
          const invalidChars = /[<>{}|\\^`]/;
          if (invalidChars.test(cleanUrl)) {
            return { valid: false, message: 'Caractères spéciaux non autorisés' };
          }

          // Vérifier l'encodage
          if (decodeURIComponent(cleanUrl) !== cleanUrl) {
            return { valid: false, message: 'URL mal encodée' };
          }

        } catch (error) {
          return { valid: false, message: 'URL invalide' };
        }
      }

      return { valid: true, message: '' };
    }, [customValidateUrl, validationLevel, allowedProtocols, blockedProtocols, requireHttps, selectedProtocol, disableTrim]);

    // ========================================================================
    // VÉRIFICATION DE DISPONIBILITÉ
    // ========================================================================

    const checkAvailability = useCallback(async (url: string) => {
      if (disableAvailabilityCheck || !url) {
        setAvailabilityStatus('unknown');
        return;
      }

      setIsChecking(true);
      setStatus('checking');

      try {
        const response = await fetch(url, {
          method: 'HEAD',
          mode: 'no-cors',
          signal: AbortSignal.timeout(5000),
        });

        setAvailabilityStatus('available');
        setStatus('valid');
      } catch (error) {
        setAvailabilityStatus('unavailable');
        setStatus('valid');
      } finally {
        setIsChecking(false);
      }
    }, [disableAvailabilityCheck]);

    // ========================================================================
    // PRÉVISUALISATION
    // ========================================================================

    const fetchPreview = useCallback(async (url: string) => {
      if (!url || !showPreview) return;

      if (customPreview) {
        try {
          const result = await customPreview(url);
          setPreview(result);
        } catch (error) {
          setPreview(null);
        }
        return;
      }

      // Prévisualisation basique
      try {
        const urlObj = new URL(url);
        const domain = urlObj.hostname;
        const favicon = `https://www.google.com/s2/favicons?domain=${domain}`;

        // Simuler une récupération de métadonnées
        // Dans une vraie application, on utiliserait une API comme OpenGraph
        setPreview({
          title: urlObj.hostname,
          description: url,
          favicon,
          site: domain,
          type: 'website',
        });
      } catch (error) {
        setPreview(null);
      }
    }, [showPreview, customPreview]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((newValue: string | null) => {
      const trimmed = newValue ? (disableTrim ? newValue : newValue.trim()) : null;
      const validation = validateUrl(trimmed || '');
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, trimmed);
      }

      if (isControlled) {
        if (onChange) onChange(trimmed);
      } else {
        setInternalValue(trimmed);
        if (onChange) onChange(trimmed);
      }

      // Mettre à jour l'affichage
      setDisplayValue(trimmed || '');

      // Vérifier la disponibilité
      if (validation.valid && trimmed) {
        checkAvailability(trimmed);
        fetchPreview(trimmed);
      } else {
        setAvailabilityStatus('unknown');
        setPreview(null);
      }

      if (debug) {
        console.log('UrlField update:', { newValue: trimmed, isValid: validation.valid });
      }
    }, [
      validateUrl,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      checkAvailability,
      fetchPreview,
      disableTrim,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      const rawValue = e.target.value;
      setDisplayValue(rawValue);

      if (!disableRealtimeValidation) {
        const trimmed = disableTrim ? rawValue : rawValue.trim();
        const validation = validateUrl(trimmed);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        if (onValidate) onValidate(validation.valid, trimmed);
        
        if (validation.valid && trimmed) {
          checkAvailability(trimmed);
          fetchPreview(trimmed);
        }
      }
    }, [disableRealtimeValidation, validateUrl, onValidate, checkAvailability, fetchPreview, disableTrim]);

    const handleFocus = useCallback(() => {
      setIsFocused(true);
      if (onFocus) onFocus();
    }, [onFocus]);

    const handleBlur = useCallback(() => {
      setIsFocused(false);

      const trimmed = disableTrim ? displayValue : displayValue.trim();
      const validation = validateUrl(trimmed);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);
      if (onValidate) onValidate(validation.valid, trimmed);

      if (validation.valid && trimmed) {
        updateValue(trimmed);
      } else if (!trimmed) {
        updateValue(null);
      } else {
        setDisplayValue(value || '');
      }

      if (onBlur) onBlur();
    }, [
      displayValue,
      validateUrl,
      onValidate,
      updateValue,
      value,
      onBlur,
      disableTrim,
    ]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const trimmed = disableTrim ? displayValue : displayValue.trim();
        const validation = validateUrl(trimmed);
        if (validation.valid) {
          updateValue(trimmed);
        }
        inputRefInternal.current?.blur();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setDisplayValue(value || '');
        inputRefInternal.current?.blur();
      }
    }, [displayValue, validateUrl, updateValue, value, disableTrim]);

    // ========================================================================
    // ACTIONS
    // ========================================================================

    const handleOpenUrl = useCallback(() => {
      if (value) {
        let url = value;
        if (!/^[a-z]+:\/\//.test(url) && !/^(mailto|tel|sms):/.test(url)) {
          url = `https://${url}`;
        }
        window.open(url, '_blank');
      }
    }, [value]);

    const handleCopyUrl = useCallback(() => {
      if (value) {
        navigator.clipboard.writeText(value);
        toast({
          title: 'Copié',
          description: 'L\'URL a été copiée dans le presse-papier',
          duration: 2000,
        });
      }
    }, [value, toast]);

    const handleProtocolChange = useCallback((protocol: UrlProtocol) => {
      setSelectedProtocol(protocol);
      const currentValue = displayValue;
      if (currentValue && !/^[a-z]+:\/\//.test(currentValue) && !/^(mailto|tel|sms):/.test(currentValue)) {
        const newValue = `${PROTOCOLS[protocol].prefix}${currentValue}`;
        setDisplayValue(newValue);
        updateValue(newValue);
      }
    }, [displayValue, updateValue]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined && externalValue !== prevValueRef.current) {
        prevValueRef.current = externalValue;
        setDisplayValue(externalValue || '');
        if (externalValue) {
          const validation = validateUrl(externalValue);
          setIsValid(validation.valid);
          setValidationMessage(validation.message);
          if (validation.valid) {
            checkAvailability(externalValue);
            fetchPreview(externalValue);
          }
        }
      }
    }, [externalValue, validateUrl, checkAvailability, fetchPreview]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue !== undefined && !isControlled) {
        const val = defaultValue;
        setDisplayValue(val || '');
        if (val) {
          const validation = validateUrl(val);
          setIsValid(validation.valid);
          setValidationMessage(validation.message);
          if (validation.valid) {
            checkAvailability(val);
            fetchPreview(val);
          }
        }
        updateValue(val);
      }
    }, [defaultValue, updateValue, isControlled, validateUrl, checkAvailability, fetchPreview]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => inputRefInternal.current?.focus(),
      blur: () => inputRefInternal.current?.blur(),
      select: () => inputRefInternal.current?.select(),
      getValue: () => value,
      setValue: (val: string | null) => updateValue(val),
      validate: () => {
        const validation = validateUrl(displayValue);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU
    // ========================================================================

    const hasError = !!error || !isValid || (required && !value);
    const isSuccess = !hasError && success && value;

    return (
      <div ref={containerRef} className="relative space-y-1.5" id={id}>
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
            {status === 'checking' && (
              <Badge variant="outline" size="sm" className="animate-pulse">
                <ArrowPathIcon className="h-3 w-3 animate-spin mr-1" />
                Vérification...
              </Badge>
            )}
          </div>
        )}

        {/* Champ de saisie */}
        <div className="relative">
          <div className={cn(
            'relative flex items-center rounded-lg border transition-all',
            hasError 
              ? 'border-red-500 ring-2 ring-red-500/20 dark:border-red-400' 
              : isSuccess && !disabled
              ? 'border-green-500 ring-2 ring-green-500/20 dark:border-green-400'
              : isFocused
              ? 'border-brand-500 ring-2 ring-brand-500/20 dark:border-brand-400'
              : 'border-gray-300 dark:border-gray-600',
            disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50'
          )}>
            {/* Protocole */}
            {showProtocol && (
              <div className="flex-shrink-0 pl-2">
                <Popover
                  trigger={
                    <button
                      type="button"
                      className="flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                      disabled={disabled}
                    >
                      <span>{PROTOCOLS[selectedProtocol]?.label || 'https'}</span>
                      <ChevronDownIcon className="h-3 w-3 text-gray-400" />
                    </button>
                  }
                  placement="bottom-start"
                  size="sm"
                >
                  <div className="p-1 max-h-48 overflow-y-auto">
                    {Object.entries(PROTOCOLS).map(([key, value]) => (
                      <button
                        key={key}
                        type="button"
                        className={cn(
                          'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
                          selectedProtocol === key
                            ? 'bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400'
                            : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                        )}
                        onClick={() => handleProtocolChange(key as UrlProtocol)}
                      >
                        <span>{value.label}</span>
                        <span className="text-xs text-gray-400">{value.prefix}</span>
                        {selectedProtocol === key && (
                          <CheckIcon className="h-4 w-4 text-brand-500 ml-auto" />
                        )}
                      </button>
                    ))}
                  </div>
                </Popover>
              </div>
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
              type="url"
              className={cn(
                'w-full bg-transparent px-3 py-2 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 outline-none',
                disabled && 'cursor-not-allowed',
                showProtocol && 'pl-2'
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
              autoComplete="url"
            />

            {/* Icônes */}
            <div className="flex items-center gap-1 pr-2">
              {showValidationIcon && (
                <>
                  {hasError && !disabled && (
                    <ExclamationCircleIcon className="h-4 w-4 text-red-500" />
                  )}
                  {isSuccess && !disabled && (
                    <CheckCircleIcon className="h-4 w-4 text-green-500" />
                  )}
                </>
              )}
              
              {showOpenButton && value && !disabled && (
                <Tooltip content="Ouvrir l'URL">
                  <button
                    type="button"
                    onClick={handleOpenUrl}
                    className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                  >
                    <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                  </button>
                </Tooltip>
              )}

              {showCopyButton && value && !disabled && (
                <Tooltip content="Copier l'URL">
                  <button
                    type="button"
                    onClick={handleCopyUrl}
                    className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                  >
                    <DocumentDuplicateIcon className="h-4 w-4" />
                  </button>
                </Tooltip>
              )}
            </div>
          </div>

          {/* Statut */}
          <div className="mt-1 flex items-center gap-1.5 text-xs">
            {hasError && (
              <span className="text-red-600 dark:text-red-400">
                {error || validationMessage || 'URL invalide'}
              </span>
            )}
            {success && !hasError && (
              <span className="text-green-600 dark:text-green-400">{success}</span>
            )}
            {info && !hasError && !success && (
              <span className="text-blue-600 dark:text-blue-400">{info}</span>
            )}
            {availabilityStatus === 'available' && !hasError && (
              <Badge variant="success" size="xs" className="ml-auto">
                Disponible
              </Badge>
            )}
            {availabilityStatus === 'unavailable' && !hasError && (
              <Badge variant="danger" size="xs" className="ml-auto">
                Indisponible
              </Badge>
            )}
          </div>
        </div>

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}

        {/* Prévisualisation */}
        {showPreview && preview && value && (
          <div className="mt-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-3">
            <div className="flex items-start gap-3">
              {showFavicon && preview.favicon && (
                <img
                  src={preview.favicon}
                  alt="Favicon"
                  className="h-6 w-6 flex-shrink-0 rounded"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                  {preview.title || preview.site || value}
                </p>
                {preview.description && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2">
                    {preview.description}
                  </p>
                )}
                {preview.site && (
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    {preview.site}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }
);

UrlField.displayName = 'UrlField';

// ============================================================================
// EXPORTS
// ============================================================================

export default UrlField;

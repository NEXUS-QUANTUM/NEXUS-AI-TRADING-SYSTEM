// apps/web/src/components/forms/fields/RichTextField.tsx
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
  BoldIcon,
  ItalicIcon,
  UnderlineIcon,
  StrikethroughIcon,
  ListBulletIcon,
  ListChevronIcon,
  AlignLeftIcon,
  AlignCenterIcon,
  AlignRightIcon,
  AlignJustifyIcon,
  LinkIcon,
  LinkSlashIcon,
  PhotoIcon,
  VideoCameraIcon,
  MusicalNoteIcon,
  DocumentTextIcon,
  CodeBracketIcon,
  QuoteIcon,
  MinusIcon,
  PlusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  XMarkIcon,
  CheckIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  EyeIcon,
  EyeSlashIcon,
  TrashIcon,
  PencilIcon,
  ClipboardIcon,
  DocumentDuplicateIcon,
  ArrowUturnLeftIcon,
  ArrowUturnRightIcon,
  SparklesIcon,
  AdjustmentsHorizontalIcon,
  Square2StackIcon,
  RectangleGroupIcon,
  TableCellsIcon,
  PaintBrushIcon,
  GlobeAltIcon,
  LinkIcon as LinkIconSolid,
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
import { Input } from '@/components/common/Input';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type RichTextFormat = 'plain' | 'html' | 'markdown' | 'json';
export type RichTextVariant = 'default' | 'compact' | 'minimal' | 'rounded' | 'outlined';
export type RichTextToolbar = 'basic' | 'standard' | 'full' | 'custom';
export type RichTextMode = 'wysiwyg' | 'source' | 'split';

export interface RichTextToolbarConfig {
  /** Afficher la barre d'outils */
  showToolbar?: boolean;
  /** Afficher les boutons de formatage de base */
  showBasic?: boolean;
  /** Afficher les boutons de liste */
  showLists?: boolean;
  /** Afficher les boutons d'alignement */
  showAlignment?: boolean;
  /** Afficher les boutons de lien */
  showLinks?: boolean;
  /** Afficher les boutons de média */
  showMedia?: boolean;
  /** Afficher les boutons de code */
  showCode?: boolean;
  /** Afficher les boutons d'historique */
  showHistory?: boolean;
  /** Afficher le sélecteur de couleur */
  showColor?: boolean;
  /** Afficher le sélecteur de taille */
  showSize?: boolean;
  /** Afficher le mode source */
  showSource?: boolean;
  /** Afficher le compteur de mots */
  showWordCount?: boolean;
}

export interface RichTextFieldProps {
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
  /** Variante d'affichage */
  variant?: RichTextVariant;
  /** Mode d'édition */
  mode?: RichTextMode;
  /** Niveau de la barre d'outils */
  toolbar?: RichTextToolbar;
  /** Configuration de la barre d'outils */
  toolbarConfig?: RichTextToolbarConfig;
  /** Format de sortie */
  outputFormat?: RichTextFormat;
  /** Hauteur minimale */
  minHeight?: string | number;
  /** Hauteur maximale */
  maxHeight?: string | number;
  /** Afficher la barre d'outils */
  showToolbar?: boolean;
  /** Afficher le compteur de caractères */
  showCharCount?: boolean;
  /** Afficher le compteur de mots */
  showWordCount?: boolean;
  /** Afficher les raccourcis */
  showShortcuts?: boolean;

  // --- Comportement ---
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Longueur maximale */
  maxLength?: number;
  /** Longueur minimale */
  minLength?: number;
  /** Désactiver les images */
  disableImages?: boolean;
  /** Désactiver les liens */
  disableLinks?: boolean;
  /** Désactiver les listes */
  disableLists?: boolean;
  /** Désactiver les tableaux */
  disableTables?: boolean;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Validation personnalisée */
  validateRichText?: (value: string) => boolean | string;

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
  customFormat?: (value: string) => string;
  /** Fonction de parsing personnalisée */
  customParse?: (value: string) => string | null;
  /** Ref */
  inputRef?: React.Ref<HTMLTextAreaElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const DEFAULT_MIN_HEIGHT = 150;
const DEFAULT_MAX_HEIGHT = 500;
const DEFAULT_MAX_LENGTH = 10000;

const TOOLBAR_BASIC = ['bold', 'italic', 'underline', 'strikethrough'];
const TOOLBAR_STANDARD = [...TOOLBAR_BASIC, 'bulletList', 'orderedList', 'link', 'quote'];
const TOOLBAR_FULL = [...TOOLBAR_STANDARD, 'alignLeft', 'alignCenter', 'alignRight', 'alignJustify', 'code', 'image', 'video', 'table', 'undo', 'redo', 'source'];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const RichTextField = forwardRef<HTMLDivElement, RichTextFieldProps>(
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
      placeholder = 'Saisissez votre texte enrichi...',
      description,
      error,
      success,
      info,
      variant = 'default',
      mode = 'wysiwyg',
      toolbar = 'standard',
      toolbarConfig = {},
      outputFormat = 'html',
      minHeight = DEFAULT_MIN_HEIGHT,
      maxHeight = DEFAULT_MAX_HEIGHT,
      showToolbar = true,
      showCharCount = true,
      showWordCount = true,
      showShortcuts = true,

      // Comportement
      disabled = false,
      required = false,
      maxLength = DEFAULT_MAX_LENGTH,
      minLength = 0,
      disableImages = false,
      disableLinks = false,
      disableLists = false,
      disableTables = false,
      disableRealtimeValidation = false,
      validateRichText: customValidate,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,
      name,

      // Avancé
      customFormat,
      customParse,
      inputRef,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const editorRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const prevValueRef = useRef<string | null>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState<string | null>(
      defaultValue || ''
    );
    const [displayValue, setDisplayValue] = useState<string>('');
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');
    const [currentMode, setCurrentMode] = useState<RichTextMode>(mode);
    const [wordCount, setWordCount] = useState(0);
    const [charCount, setCharCount] = useState(0);
    const [isLoading, setIsLoading] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const hasValue = value && value.length > 0;

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateValue = useCallback((val: string | null): { valid: boolean; message: string } => {
      if (customValidate) {
        const result = customValidate(val || '');
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (!val || val.trim() === '') {
        if (required) {
          return { valid: false, message: 'Le texte enrichi est requis' };
        }
        return { valid: true, message: '' };
      }

      const cleanText = val.replace(/<[^>]*>/g, '').trim();
      const length = cleanText.length;

      if (length < minLength) {
        return { valid: false, message: `Le texte doit contenir au moins ${minLength} caractères` };
      }

      if (length > maxLength) {
        return { valid: false, message: `Le texte ne doit pas dépasser ${maxLength} caractères` };
      }

      return { valid: true, message: '' };
    }, [customValidate, required, minLength, maxLength]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((val: string | null) => {
      const validation = validateValue(val);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, val);
      }

      if (isControlled) {
        if (onChange) onChange(val);
      } else {
        setInternalValue(val);
        if (onChange) onChange(val);
      }

      // Mettre à jour les compteurs
      if (val) {
        const cleanText = val.replace(/<[^>]*>/g, '').trim();
        setCharCount(cleanText.length);
        setWordCount(cleanText.split(/\s+/).filter(w => w.length > 0).length);
      } else {
        setCharCount(0);
        setWordCount(0);
      }

      setDisplayValue(val || '');

      if (debug) {
        console.log('RichTextField update:', { val, isValid: validation.valid });
      }
    }, [
      validateValue,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      debug,
    ]);

    // ========================================================================
    // SYNCHRONISATION DE L'ÉDITEUR
    // ========================================================================

    const syncEditor = useCallback(() => {
      if (editorRef.current && currentMode !== 'source') {
        const content = editorRef.current.innerHTML;
        updateValue(content);
      }
    }, [currentMode, updateValue]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const rawValue = e.target.value;
      setDisplayValue(rawValue);
      updateValue(rawValue);
    }, [updateValue]);

    const handleFocus = useCallback(() => {
      setIsFocused(true);
      if (onFocus) onFocus();
    }, [onFocus]);

    const handleBlur = useCallback(() => {
      setIsFocused(false);
      if (onBlur) onBlur();
    }, [onBlur]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
        // Empêcher la soumission du formulaire par Enter
        e.preventDefault();
        document.execCommand('insertLineBreak', false);
      }
    }, []);

    // ========================================================================
    // ACTIONS DE L'ÉDITEUR
    // ========================================================================

    const execCommand = useCallback((command: string, value?: string) => {
      if (disabled) return;

      document.execCommand(command, false, value || '');
      syncEditor();

      if (debug) {
        console.log('RichTextField execCommand:', { command, value });
      }
    }, [disabled, syncEditor, debug]);

    const handleBold = useCallback(() => execCommand('bold'), [execCommand]);
    const handleItalic = useCallback(() => execCommand('italic'), [execCommand]);
    const handleUnderline = useCallback(() => execCommand('underline'), [execCommand]);
    const handleStrikethrough = useCallback(() => execCommand('strikethrough'), [execCommand]);

    const handleBulletList = useCallback(() => execCommand('insertUnorderedList'), [execCommand]);
    const handleOrderedList = useCallback(() => execCommand('insertOrderedList'), [execCommand]);

    const handleAlignLeft = useCallback(() => execCommand('justifyLeft'), [execCommand]);
    const handleAlignCenter = useCallback(() => execCommand('justifyCenter'), [execCommand]);
    const handleAlignRight = useCallback(() => execCommand('justifyRight'), [execCommand]);
    const handleAlignJustify = useCallback(() => execCommand('justifyFull'), [execCommand]);

    const handleUndo = useCallback(() => execCommand('undo'), [execCommand]);
    const handleRedo = useCallback(() => execCommand('redo'), [execCommand]);

    const handleLink = useCallback(() => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed) {
        toast({
          title: 'Aucune sélection',
          description: 'Veuillez sélectionner du texte pour créer un lien',
          variant: 'default',
        });
        return;
      }

      const url = window.prompt('Entrez l\'URL:', 'https://');
      if (url) {
        execCommand('createLink', url);
      }
    }, [execCommand, toast]);

    const handleUnlink = useCallback(() => execCommand('unlink'), [execCommand]);

    const handleQuote = useCallback(() => execCommand('formatBlock', 'blockquote'), [execCommand]);

    const handleImage = useCallback(() => {
      if (disableImages) return;

      const url = window.prompt('Entrez l\'URL de l\'image:', 'https://');
      if (url) {
        execCommand('insertImage', url);
      }
    }, [disableImages, execCommand]);

    const handleTable = useCallback(() => {
      if (disableTables) return;

      const rows = prompt('Nombre de lignes:', '3');
      const cols = prompt('Nombre de colonnes:', '3');
      if (rows && cols) {
        let table = '<table border="1" cellpadding="5" cellspacing="0">';
        for (let i = 0; i < parseInt(rows); i++) {
          table += '<tr>';
          for (let j = 0; j < parseInt(cols); j++) {
            table += '<td>&nbsp;</td>';
          }
          table += '</tr>';
        }
        table += '</table>';
        execCommand('insertHTML', table);
      }
    }, [disableTables, execCommand]);

    const handleCode = useCallback(() => {
      execCommand('formatBlock', 'pre');
    }, [execCommand]);

    const handleClear = useCallback(() => {
      if (confirm('Voulez-vous effacer tout le contenu ?')) {
        updateValue('');
        if (editorRef.current) {
          editorRef.current.innerHTML = '';
        }
        toast({
          title: 'Contenu effacé',
          description: 'Le contenu a été effacé avec succès',
          duration: 2000,
        });
      }
    }, [updateValue, toast]);

    const handleToggleMode = useCallback(() => {
      if (currentMode === 'wysiwyg') {
        setCurrentMode('source');
        setDisplayValue(value || '');
      } else {
        setCurrentMode('wysiwyg');
        updateValue(displayValue);
      }
    }, [currentMode, value, displayValue, updateValue]);

    // ========================================================================
    // RACCOURCIS CLAVIER
    // ========================================================================

    useEffect(() => {
      const handleKeyboardShortcuts = (e: KeyboardEvent) => {
        if (!isFocused) return;

        const ctrl = e.ctrlKey || e.metaKey;

        if (ctrl && e.key === 'b') { e.preventDefault(); handleBold(); }
        if (ctrl && e.key === 'i') { e.preventDefault(); handleItalic(); }
        if (ctrl && e.key === 'u') { e.preventDefault(); handleUnderline(); }
        if (ctrl && e.key === 'z') { e.preventDefault(); handleUndo(); }
        if (ctrl && e.shiftKey && e.key === 'z') { e.preventDefault(); handleRedo(); }
        if (ctrl && e.key === 'k') { e.preventDefault(); handleLink(); }
      };

      document.addEventListener('keydown', handleKeyboardShortcuts);
      return () => document.removeEventListener('keydown', handleKeyboardShortcuts);
    }, [isFocused, handleBold, handleItalic, handleUnderline, handleUndo, handleRedo, handleLink]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue !== undefined && !isControlled) {
        updateValue(defaultValue);
      }
    }, [defaultValue, updateValue, isControlled]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined && externalValue !== prevValueRef.current) {
        prevValueRef.current = externalValue;
        setDisplayValue(externalValue || '');
        if (editorRef.current && currentMode === 'wysiwyg') {
          editorRef.current.innerHTML = externalValue || '';
        }
        if (externalValue) {
          const validation = validateValue(externalValue);
          setIsValid(validation.valid);
          setValidationMessage(validation.message);
        }
      }
    }, [externalValue, validateValue, currentMode]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => {
        if (currentMode === 'source') {
          textareaRef.current?.focus();
        } else {
          editorRef.current?.focus();
        }
      },
      blur: () => {
        if (currentMode === 'source') {
          textareaRef.current?.blur();
        } else {
          editorRef.current?.blur();
        }
      },
      getValue: () => value,
      setValue: (val: string | null) => updateValue(val),
      clear: () => updateValue(''),
      validate: () => {
        const validation = validateValue(value);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU DE LA BARRE D'OUTILS
    // ========================================================================

    const renderToolbar = () => {
      if (!showToolbar) return null;

      const config = toolbarConfig;
      const showBasic = config.showBasic !== undefined ? config.showBasic : true;
      const showLists = config.showLists !== undefined ? config.showLists : true;
      const showAlignment = config.showAlignment !== undefined ? config.showAlignment : true;
      const showLinks = config.showLinks !== undefined ? config.showLinks : true;
      const showMedia = config.showMedia !== undefined ? config.showMedia : true;
      const showCode = config.showCode !== undefined ? config.showCode : true;
      const showHistory = config.showHistory !== undefined ? config.showHistory : true;
      const showColor = config.showColor !== undefined ? config.showColor : false;
      const showSize = config.showSize !== undefined ? config.showSize : false;
      const showSource = config.showSource !== undefined ? config.showSource : true;

      return (
        <div className={cn(
          'flex flex-wrap items-center gap-0.5 p-1 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50',
          variant === 'rounded' && 'rounded-t-lg',
          variant === 'minimal' && 'border-b-2'
        )}>
          {/* Formatage de base */}
          {showBasic && (
            <>
              <Tooltip content="Gras (Ctrl+B)">
                <button
                  type="button"
                  onClick={handleBold}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <BoldIcon className="h-4 w-4" />
                </button>
              </Tooltip>
              <Tooltip content="Italique (Ctrl+I)">
                <button
                  type="button"
                  onClick={handleItalic}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <ItalicIcon className="h-4 w-4" />
                </button>
              </Tooltip>
              <Tooltip content="Souligné (Ctrl+U)">
                <button
                  type="button"
                  onClick={handleUnderline}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <UnderlineIcon className="h-4 w-4" />
                </button>
              </Tooltip>
              <Tooltip content="Barré">
                <button
                  type="button"
                  onClick={handleStrikethrough}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <StrikethroughIcon className="h-4 w-4" />
                </button>
              </Tooltip>
            </>
          )}

          {/* Séparateur */}
          <span className="w-px h-6 bg-gray-300 dark:bg-gray-600 mx-0.5" />

          {/* Listes */}
          {showLists && !disableLists && (
            <>
              <Tooltip content="Liste à puces">
                <button
                  type="button"
                  onClick={handleBulletList}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <ListBulletIcon className="h-4 w-4" />
                </button>
              </Tooltip>
              <Tooltip content="Liste numérotée">
                <button
                  type="button"
                  onClick={handleOrderedList}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <ListChevronIcon className="h-4 w-4" />
                </button>
              </Tooltip>
            </>
          )}

          {/* Séparateur */}
          <span className="w-px h-6 bg-gray-300 dark:bg-gray-600 mx-0.5" />

          {/* Alignement */}
          {showAlignment && (
            <>
              <Tooltip content="Aligner à gauche">
                <button
                  type="button"
                  onClick={handleAlignLeft}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <AlignLeftIcon className="h-4 w-4" />
                </button>
              </Tooltip>
              <Tooltip content="Centrer">
                <button
                  type="button"
                  onClick={handleAlignCenter}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <AlignCenterIcon className="h-4 w-4" />
                </button>
              </Tooltip>
              <Tooltip content="Aligner à droite">
                <button
                  type="button"
                  onClick={handleAlignRight}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <AlignRightIcon className="h-4 w-4" />
                </button>
              </Tooltip>
              <Tooltip content="Justifier">
                <button
                  type="button"
                  onClick={handleAlignJustify}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <AlignJustifyIcon className="h-4 w-4" />
                </button>
              </Tooltip>
            </>
          )}

          {/* Séparateur */}
          <span className="w-px h-6 bg-gray-300 dark:bg-gray-600 mx-0.5" />

          {/* Liens */}
          {showLinks && !disableLinks && (
            <>
              <Tooltip content="Ajouter un lien (Ctrl+K)">
                <button
                  type="button"
                  onClick={handleLink}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <LinkIcon className="h-4 w-4" />
                </button>
              </Tooltip>
              <Tooltip content="Supprimer le lien">
                <button
                  type="button"
                  onClick={handleUnlink}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <LinkSlashIcon className="h-4 w-4" />
                </button>
              </Tooltip>
            </>
          )}

          {/* Séparateur */}
          <span className="w-px h-6 bg-gray-300 dark:bg-gray-600 mx-0.5" />

          {/* Médias */}
          {showMedia && (
            <>
              {!disableImages && (
                <Tooltip content="Insérer une image">
                  <button
                    type="button"
                    onClick={handleImage}
                    className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                    disabled={disabled || currentMode === 'source'}
                  >
                    <PhotoIcon className="h-4 w-4" />
                  </button>
                </Tooltip>
              )}
              <Tooltip content="Citation">
                <button
                  type="button"
                  onClick={handleQuote}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <QuoteIcon className="h-4 w-4" />
                </button>
              </Tooltip>
            </>
          )}

          {/* Séparateur */}
          <span className="w-px h-6 bg-gray-300 dark:bg-gray-600 mx-0.5" />

          {/* Code */}
          {showCode && (
            <Tooltip content="Code">
              <button
                type="button"
                onClick={handleCode}
                className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                disabled={disabled || currentMode === 'source'}
              >
                <CodeBracketIcon className="h-4 w-4" />
              </button>
            </Tooltip>
          )}

          {/* Tables */}
          {!disableTables && (
            <Tooltip content="Tableau">
              <button
                type="button"
                onClick={handleTable}
                className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                disabled={disabled || currentMode === 'source'}
              >
                <TableCellsIcon className="h-4 w-4" />
              </button>
            </Tooltip>
          )}

          {/* Séparateur */}
          <span className="w-px h-6 bg-gray-300 dark:bg-gray-600 mx-0.5" />

          {/* Historique */}
          {showHistory && (
            <>
              <Tooltip content="Annuler (Ctrl+Z)">
                <button
                  type="button"
                  onClick={handleUndo}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <ArrowUturnLeftIcon className="h-4 w-4" />
                </button>
              </Tooltip>
              <Tooltip content="Rétablir (Ctrl+Maj+Z)">
                <button
                  type="button"
                  onClick={handleRedo}
                  className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
                  disabled={disabled || currentMode === 'source'}
                >
                  <ArrowUturnRightIcon className="h-4 w-4" />
                </button>
              </Tooltip>
            </>
          )}

          {/* Séparateur */}
          <span className="w-px h-6 bg-gray-300 dark:bg-gray-600 mx-0.5" />

          {/* Mode source */}
          {showSource && (
            <Tooltip content={currentMode === 'source' ? 'Mode visuel' : 'Mode source'}>
              <button
                type="button"
                onClick={handleToggleMode}
                className={cn(
                  'rounded p-1.5 transition-colors',
                  currentMode === 'source' ? 'bg-brand-500 text-white' : 'hover:bg-gray-200 dark:hover:bg-gray-700'
                )}
                disabled={disabled}
              >
                <CodeBracketIcon className="h-4 w-4" />
              </button>
            </Tooltip>
          )}

          {/* Effacer */}
          <Tooltip content="Effacer tout">
            <button
              type="button"
              onClick={handleClear}
              className="rounded p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50 text-red-500"
              disabled={disabled}
            >
              <TrashIcon className="h-4 w-4" />
            </button>
          </Tooltip>

          {/* Espace flexible */}
          <div className="flex-1" />

          {/* Compteurs */}
          {showWordCount && (
            <span className="text-xs text-gray-400 dark:text-gray-500">
              {wordCount} mots
            </span>
          )}
          {showCharCount && (
            <span className="text-xs text-gray-400 dark:text-gray-500 ml-2">
              {charCount} caractères
              {maxLength && ` / ${maxLength}`}
            </span>
          )}
        </div>
      );
    };

    // ========================================================================
    // RENDU DE L'ÉDITEUR
    // ========================================================================

    const renderEditor = () => {
      if (currentMode === 'source') {
        return (
          <textarea
            ref={(node) => {
              textareaRef.current = node;
              if (inputRef) {
                if (typeof inputRef === 'function') {
                  inputRef(node);
                } else {
                  (inputRef as React.MutableRefObject<HTMLTextAreaElement>).current = node;
                }
              }
            }}
            id={id || name}
            className={cn(
              'w-full resize-y bg-transparent px-3 py-2 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 outline-none font-mono text-sm',
              disabled && 'cursor-not-allowed',
              variant === 'compact' && 'text-xs',
              variant === 'rounded' && 'rounded-b-lg'
            )}
            value={displayValue}
            onChange={handleChange}
            onFocus={handleFocus}
            onBlur={handleBlur}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            required={required}
            placeholder={placeholder}
            aria-label={ariaLabel || label}
            aria-describedby={ariaDescribedby}
            aria-invalid={!isValid}
            aria-required={required}
            name={name}
            style={{
              minHeight: typeof minHeight === 'number' ? `${minHeight}px` : minHeight,
              maxHeight: typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight,
            }}
          />
        );
      }

      return (
        <div
          ref={editorRef}
          contentEditable={!disabled}
          className={cn(
            'prose prose-sm dark:prose-invert max-w-none min-h-[100px] w-full overflow-y-auto px-3 py-2 text-gray-900 dark:text-white outline-none focus:ring-0 focus:border-brand-500',
            disabled && 'cursor-not-allowed opacity-50',
            variant === 'compact' && 'text-xs',
            variant === 'rounded' && 'rounded-b-lg'
          )}
          onInput={syncEditor}
          onFocus={handleFocus}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          dangerouslySetInnerHTML={{ __html: value || '' }}
          style={{
            minHeight: typeof minHeight === 'number' ? `${minHeight}px` : minHeight,
            maxHeight: typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight,
          }}
          placeholder={placeholder}
        />
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const hasError = !!error || !isValid || (required && !value);
    const isSuccess = !hasError && success && value;

    return (
      <div ref={containerRef} className="relative space-y-1.5" id={id}>
        {/* Label */}
        {label && (
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {label}
              {required && <span className="ml-1 text-red-500">*</span>}
            </Label>
            {showShortcuts && (
              <Badge variant="outline" size="xs" className="text-xs">
                ⌘B, ⌘I, ⌘U, ⌘K
              </Badge>
            )}
          </div>
        )}

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}

        {/* Éditeur */}
        <div className={cn(
          'relative rounded-lg border transition-all overflow-hidden',
          hasError 
            ? 'border-red-500 ring-2 ring-red-500/20 dark:border-red-400' 
            : isSuccess && !disabled
            ? 'border-green-500 ring-2 ring-green-500/20 dark:border-green-400'
            : isFocused
            ? 'border-brand-500 ring-2 ring-brand-500/20 dark:border-brand-400'
            : 'border-gray-300 dark:border-gray-600',
          disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50',
          variant === 'rounded' && 'rounded-lg',
          variant === 'minimal' && 'rounded-none border-0 border-b-2'
        )}>
          {/* Barre d'outils */}
          {renderToolbar()}

          {/* Éditeur */}
          {renderEditor()}

          {/* Statut */}
          <div className="mt-1 flex items-center gap-1.5 text-xs px-3 pb-1">
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
      </div>
    );
  }
);

RichTextField.displayName = 'RichTextField';

// ============================================================================
// EXPORTS
// ============================================================================

export default RichTextField;

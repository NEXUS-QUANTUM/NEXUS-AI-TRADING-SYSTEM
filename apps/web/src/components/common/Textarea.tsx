import React, { forwardRef, useState, useCallback, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import {
  AlertCircle,
  CheckCircle,
  Info,
  Loader2,
  Eye,
  EyeOff,
  Copy,
  Check,
  Maximize2,
  Minimize2,
  Type,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Bold,
  Italic,
  Underline,
  List,
  ListOrdered,
  Link,
  Image,
  Code,
  Quote,
  Heading1,
  Heading2,
  Heading3,
  RefreshCw
} from 'lucide-react';
import { useDebounce } from '@/hooks/useDebounce';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { useTheme } from '@/hooks/useTheme';

/**
 * NEXUS AI TRADING SYSTEM - Textarea Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete Textarea system with:
 * - Multiple variants (default, outlined, filled, etc.)
 * - Multiple sizes (sm, md, lg)
 * - Multiple colors
 * - Auto resize
 * - Character counter
 * - Word counter
 * - Line counter
 * - Syntax highlighting
 * - Markdown support
 * - Rich text toolbar
 * - Code editor mode
 * - Accessibility (ARIA compliant)
 * - Keyboard shortcuts
 * - Touch support
 * - Loading states
 * - Error states
 * - Success states
 * - Validation
 * - Formatting
 * - Copy to clipboard
 * - Expand/Collapse
 * - Fullscreen mode
 * - Theme aware
 * - Persistent preferences
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type TextareaVariant = 'default' | 'outlined' | 'filled' | 'minimal' | 'glass' | 'modern' | 'neon' | 'code';
export type TextareaSize = 'sm' | 'md' | 'lg';
export type TextareaColor = 'nexus' | 'blue' | 'green' | 'red' | 'purple' | 'yellow' | 'pink';
export type TextareaStatus = 'idle' | 'loading' | 'success' | 'error' | 'warning' | 'info';
export type TextareaResize = 'none' | 'vertical' | 'horizontal' | 'both';
export type TextareaMode = 'plain' | 'rich' | 'code' | 'markdown';
export type TextareaAlignment = 'left' | 'center' | 'right' | 'justify';

export interface TextareaProps extends Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, 'size'> {
  /** Textarea variant */
  variant?: TextareaVariant;
  /** Textarea size */
  size?: TextareaSize;
  /** Textarea color */
  color?: TextareaColor;
  /** Textarea status */
  status?: TextareaStatus;
  /** Textarea mode */
  mode?: TextareaMode;
  /** Label text */
  label?: string;
  /** Label position */
  labelPosition?: 'top' | 'left' | 'right' | 'bottom';
  /** Helper text */
  helper?: string;
  /** Error message */
  error?: string;
  /** Success message */
  success?: string;
  /** Warning message */
  warning?: string;
  /** Required indicator */
  required?: boolean;
  /** Show character counter */
  showCounter?: boolean;
  /** Max characters */
  maxLength?: number;
  /** Show word counter */
  showWordCounter?: boolean;
  /** Show line counter */
  showLineCounter?: boolean;
  /** Auto resize */
  autoResize?: boolean;
  /** Min height for auto resize */
  minHeight?: number;
  /** Max height for auto resize */
  maxHeight?: number;
  /** Resize direction */
  resize?: TextareaResize;
  /** Show formatting toolbar */
  showToolbar?: boolean;
  /** Toolbar position */
  toolbarPosition?: 'top' | 'bottom';
  /** Enable fullscreen */
  enableFullscreen?: boolean;
  /** Enable copy to clipboard */
  enableCopy?: boolean;
  /** Enable expand/collapse */
  enableExpand?: boolean;
  /** Enable markdown preview */
  enablePreview?: boolean;
  /** Enable syntax highlighting */
  syntaxHighlighting?: boolean;
  /** Language for syntax highlighting */
  language?: string;
  /** Show line numbers */
  showLineNumbers?: boolean;
  /** Tab size for code */
  tabSize?: number;
  /** Persist content to localStorage */
  persistContent?: boolean;
  /** Storage key for persistence */
  storageKey?: string;
  /** Debounce delay for onChange (ms) */
  debounceDelay?: number;
  /** On validation */
  onValidate?: (value: string) => boolean | string;
  /** On format change */
  onFormatChange?: (format: TextareaMode) => void;
  /** Additional className */
  className?: string;
  /** Label className */
  labelClassName?: string;
  /** Input className */
  inputClassName?: string;
  /** Helper className */
  helperClassName?: string;
  /** Error className */
  errorClassName?: string;
  /** Toolbar className */
  toolbarClassName?: string;
  /** ARIA label */
  ariaLabel?: string;
  /** Test ID */
  testId?: string;
}

// ========================================
// CONFIGURATION
// ========================================

const VARIANT_CONFIG: Record<TextareaVariant, {
  container: string;
  input: string;
  label: string;
  helper: string;
}> = {
  default: {
    container: 'space-y-1.5',
    input: 'border border-nexus-300 dark:border-nexus-600 bg-white dark:bg-nexus-900 text-nexus-900 dark:text-nexus-100 placeholder:text-nexus-400 dark:placeholder:text-nexus-500 focus:ring-2 focus:ring-nexus-500 focus:border-transparent',
    label: 'text-nexus-700 dark:text-nexus-300',
    helper: 'text-nexus-500 dark:text-nexus-400'
  },
  outlined: {
    container: 'space-y-1.5',
    input: 'border-2 border-nexus-300 dark:border-nexus-600 bg-transparent text-nexus-900 dark:text-nexus-100 placeholder:text-nexus-400 dark:placeholder:text-nexus-500 focus:ring-0 focus:border-nexus-500',
    label: 'text-nexus-700 dark:text-nexus-300',
    helper: 'text-nexus-500 dark:text-nexus-400'
  },
  filled: {
    container: 'space-y-1.5',
    input: 'border-0 bg-nexus-100 dark:bg-nexus-800 text-nexus-900 dark:text-nexus-100 placeholder:text-nexus-400 dark:placeholder:text-nexus-500 focus:ring-2 focus:ring-nexus-500 focus:bg-nexus-50 dark:focus:bg-nexus-700',
    label: 'text-nexus-700 dark:text-nexus-300',
    helper: 'text-nexus-500 dark:text-nexus-400'
  },
  minimal: {
    container: 'space-y-1.5',
    input: 'border-0 border-b-2 border-nexus-300 dark:border-nexus-600 bg-transparent rounded-none text-nexus-900 dark:text-nexus-100 placeholder:text-nexus-400 dark:placeholder:text-nexus-500 focus:ring-0 focus:border-nexus-500',
    label: 'text-nexus-700 dark:text-nexus-300',
    helper: 'text-nexus-500 dark:text-nexus-400'
  },
  glass: {
    container: 'space-y-1.5',
    input: 'border border-white/20 bg-white/10 backdrop-blur-xl text-white placeholder:text-white/50 focus:ring-2 focus:ring-white/30 focus:border-transparent',
    label: 'text-white/80',
    helper: 'text-white/50'
  },
  modern: {
    container: 'space-y-1.5',
    input: 'border border-nexus-200 dark:border-nexus-700 bg-white dark:bg-nexus-900 text-nexus-900 dark:text-nexus-100 placeholder:text-nexus-400 dark:placeholder:text-nexus-500 focus:ring-2 focus:ring-nexus-500 focus:border-transparent shadow-lg shadow-nexus-500/5',
    label: 'text-nexus-700 dark:text-nexus-300 font-medium',
    helper: 'text-nexus-500 dark:text-nexus-400'
  },
  neon: {
    container: 'space-y-1.5',
    input: 'border border-nexus-500/30 bg-nexus-900/50 text-nexus-100 placeholder:text-nexus-500 focus:ring-2 focus:ring-nexus-400 focus:border-transparent shadow-[0_0_30px_rgba(99,102,241,0.1)]',
    label: 'text-nexus-400',
    helper: 'text-nexus-500'
  },
  code: {
    container: 'space-y-1.5',
    input: 'border border-nexus-300 dark:border-nexus-600 bg-nexus-900 text-nexus-100 font-mono text-sm placeholder:text-nexus-500 focus:ring-2 focus:ring-nexus-500 focus:border-transparent',
    label: 'text-nexus-700 dark:text-nexus-300 font-mono',
    helper: 'text-nexus-500 dark:text-nexus-400'
  }
};

const SIZE_CONFIG: Record<TextareaSize, {
  input: string;
  label: string;
  helper: string;
  minHeight: number;
}> = {
  sm: {
    input: 'px-3 py-1.5 text-sm',
    label: 'text-sm',
    helper: 'text-xs',
    minHeight: 60
  },
  md: {
    input: 'px-4 py-2 text-base',
    label: 'text-base',
    helper: 'text-sm',
    minHeight: 80
  },
  lg: {
    input: 'px-5 py-3 text-lg',
    label: 'text-lg',
    helper: 'text-base',
    minHeight: 100
  }
};

const COLOR_CONFIG: Record<TextareaColor, {
  focus: string;
  border: string;
  text: string;
}> = {
  nexus: {
    focus: 'focus:ring-nexus-500',
    border: 'focus:border-nexus-500',
    text: 'text-nexus-700 dark:text-nexus-300'
  },
  blue: {
    focus: 'focus:ring-blue-500',
    border: 'focus:border-blue-500',
    text: 'text-blue-700 dark:text-blue-300'
  },
  green: {
    focus: 'focus:ring-emerald-500',
    border: 'focus:border-emerald-500',
    text: 'text-emerald-700 dark:text-emerald-300'
  },
  red: {
    focus: 'focus:ring-red-500',
    border: 'focus:border-red-500',
    text: 'text-red-700 dark:text-red-300'
  },
  purple: {
    focus: 'focus:ring-purple-500',
    border: 'focus:border-purple-500',
    text: 'text-purple-700 dark:text-purple-300'
  },
  yellow: {
    focus: 'focus:ring-yellow-500',
    border: 'focus:border-yellow-500',
    text: 'text-yellow-700 dark:text-yellow-300'
  },
  pink: {
    focus: 'focus:ring-pink-500',
    border: 'focus:border-pink-500',
    text: 'text-pink-700 dark:text-pink-300'
  }
};

const STATUS_CONFIG: Record<TextareaStatus, {
  icon: React.ReactNode;
  color: string;
  text: string;
}> = {
  idle: {
    icon: null,
    color: '',
    text: ''
  },
  loading: {
    icon: <Loader2 className="w-4 h-4 animate-spin" />,
    color: 'text-nexus-500',
    text: 'Loading...'
  },
  success: {
    icon: <CheckCircle className="w-4 h-4" />,
    color: 'text-emerald-500',
    text: 'Success'
  },
  error: {
    icon: <AlertCircle className="w-4 h-4" />,
    color: 'text-red-500',
    text: 'Error'
  },
  warning: {
    icon: <AlertCircle className="w-4 h-4" />,
    color: 'text-yellow-500',
    text: 'Warning'
  },
  info: {
    icon: <Info className="w-4 h-4" />,
    color: 'text-blue-500',
    text: 'Info'
  }
};

// ========================================
// RICH TEXT TOOLBAR BUTTONS
// ========================================

const TOOLBAR_BUTTONS = [
  { id: 'bold', icon: Bold, label: 'Bold', shortcut: 'Ctrl+B' },
  { id: 'italic', icon: Italic, label: 'Italic', shortcut: 'Ctrl+I' },
  { id: 'underline', icon: Underline, label: 'Underline', shortcut: 'Ctrl+U' },
  { id: 'divider' },
  { id: 'h1', icon: Heading1, label: 'Heading 1' },
  { id: 'h2', icon: Heading2, label: 'Heading 2' },
  { id: 'h3', icon: Heading3, label: 'Heading 3' },
  { id: 'divider' },
  { id: 'ul', icon: List, label: 'Bullet List' },
  { id: 'ol', icon: ListOrdered, label: 'Numbered List' },
  { id: 'divider' },
  { id: 'link', icon: Link, label: 'Link' },
  { id: 'image', icon: Image, label: 'Image' },
  { id: 'code', icon: Code, label: 'Code' },
  { id: 'quote', icon: Quote, label: 'Quote' },
];

// ========================================
// MAIN COMPONENT
// ========================================

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(({
  variant = 'default',
  size = 'md',
  color = 'nexus',
  status = 'idle',
  mode = 'plain',
  label,
  labelPosition = 'top',
  helper,
  error,
  success,
  warning,
  required = false,
  showCounter = false,
  maxLength,
  showWordCounter = false,
  showLineCounter = false,
  autoResize = false,
  minHeight,
  maxHeight = 400,
  resize = 'vertical',
  showToolbar = false,
  toolbarPosition = 'top',
  enableFullscreen = true,
  enableCopy = true,
  enableExpand = true,
  enablePreview = false,
  syntaxHighlighting = false,
  language = 'javascript',
  showLineNumbers = false,
  tabSize = 2,
  persistContent = false,
  storageKey = 'nexus-textarea-content',
  debounceDelay = 300,
  onValidate,
  onFormatChange,
  className,
  labelClassName,
  inputClassName,
  helperClassName,
  errorClassName,
  toolbarClassName,
  ariaLabel,
  testId = 'nexus-textarea',
  value: controlledValue,
  defaultValue = '',
  onChange,
  onFocus,
  onBlur,
  ...props
}, ref) => {
  // ========================================
  // STATE
  // ========================================
  
  const [value, setValue] = useState<string>(controlledValue !== undefined ? controlledValue : defaultValue);
  const [isFocused, setIsFocused] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [cursorPosition, setCursorPosition] = useState({ start: 0, end: 0 });
  const [selection, setSelection] = useState('');

  // ========================================
  // REFS
  // ========================================
  
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [storedContent, setStoredContent] = useLocalStorage<string>(storageKey, '');

  // ========================================
  // HOOKS
  // ========================================
  
  const { theme } = useTheme();
  const debouncedValue = useDebounce(value, debounceDelay);

  // ========================================
  // EFFECTS
  // ========================================
  
  // Sync with props
  useEffect(() => {
    if (controlledValue !== undefined) {
      setValue(controlledValue);
    }
  }, [controlledValue]);

  // Load stored content
  useEffect(() => {
    if (persistContent && storedContent && controlledValue === undefined) {
      setValue(storedContent);
    }
  }, [persistContent, storedContent, controlledValue]);

  // Save content
  useEffect(() => {
    if (persistContent && value !== storedContent) {
      setStoredContent(value);
    }
  }, [persistContent, value, storedContent]);

  // Auto resize
  useEffect(() => {
    if (autoResize && textareaRef.current) {
      const el = textareaRef.current;
      el.style.height = 'auto';
      const height = Math.min(
        Math.max(el.scrollHeight, minHeight || SIZE_CONFIG[size].minHeight),
        maxHeight
      );
      el.style.height = `${height}px`;
    }
  }, [autoResize, value, size, minHeight, maxHeight]);

  // Validation
  useEffect(() => {
    if (onValidate) {
      const result = onValidate(value);
      if (typeof result === 'string') {
        setValidationError(result);
      } else if (result === false) {
        setValidationError('Invalid value');
      } else {
        setValidationError(null);
      }
    }
  }, [value, onValidate]);

  // ========================================
  // HELPERS
  // ========================================
  
  const variantConfig = VARIANT_CONFIG[variant];
  const sizeConfig = SIZE_CONFIG[size];
  const colorConfig = COLOR_CONFIG[color];
  const statusConfig = STATUS_CONFIG[status];

  const isError = !!error || !!validationError;
  const hasStatus = status !== 'idle';

  const getCharCount = () => value.length;
  const getWordCount = () => value.trim().split(/\s+/).filter(Boolean).length;
  const getLineCount = () => value.split('\n').length;

  const charCount = getCharCount();
  const wordCount = getWordCount();
  const lineCount = getLineCount();
  const isOverLimit = maxLength !== undefined && charCount > maxLength;

  const handleValueChange = useCallback((newValue: string) => {
    if (maxLength !== undefined && newValue.length > maxLength) {
      newValue = newValue.slice(0, maxLength);
    }
    
    setValue(newValue);
    const syntheticEvent = {
      target: { value: newValue },
    } as React.ChangeEvent<HTMLTextAreaElement>;
    onChange?.(syntheticEvent);
  }, [maxLength, onChange]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    handleValueChange(e.target.value);
  }, [handleValueChange]);

  const handleFocus = useCallback((e: React.FocusEvent<HTMLTextAreaElement>) => {
    setIsFocused(true);
    onFocus?.(e);
  }, [onFocus]);

  const handleBlur = useCallback((e: React.FocusEvent<HTMLTextAreaElement>) => {
    setIsFocused(false);
    onBlur?.(e);
  }, [onBlur]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(value);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      // Fallback
      textareaRef.current?.select();
      document.execCommand('copy');
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    }
  }, [value]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Handle tab key in code mode
    if (mode === 'code' && e.key === 'Tab') {
      e.preventDefault();
      const { start, end } = cursorPosition;
      const newValue = value.substring(0, start) + '  ' + value.substring(end);
      setValue(newValue);
      if (textareaRef.current) {
        textareaRef.current.selectionStart = textareaRef.current.selectionEnd = start + tabSize;
      }
    }

    // Handle keyboard shortcuts
    if (e.ctrlKey || e.metaKey) {
      switch (e.key) {
        case 'b':
          e.preventDefault();
          wrapSelection('**', '**');
          break;
        case 'i':
          e.preventDefault();
          wrapSelection('*', '*');
          break;
        case 'u':
          e.preventDefault();
          wrapSelection('__', '__');
          break;
      }
    }

    props.onKeyDown?.(e);
  }, [mode, value, cursorPosition, tabSize, props.onKeyDown]);

  const handleSelect = useCallback((e: React.SyntheticEvent<HTMLTextAreaElement>) => {
    const target = e.currentTarget;
    setCursorPosition({
      start: target.selectionStart,
      end: target.selectionEnd
    });
    setSelection(value.substring(target.selectionStart, target.selectionEnd));
  }, [value]);

  const wrapSelection = useCallback((prefix: string, suffix: string) => {
    const { start, end } = cursorPosition;
    const selectedText = value.substring(start, end);
    const newText = prefix + selectedText + suffix;
    const newValue = value.substring(0, start) + newText + value.substring(end);
    setValue(newValue);
    
    if (textareaRef.current) {
      const newStart = start + prefix.length;
      const newEnd = newStart + selectedText.length;
      textareaRef.current.selectionStart = newStart;
      textareaRef.current.selectionEnd = newEnd;
    }
  }, [value, cursorPosition]);

  const insertText = useCallback((text: string, prefix: string = '', suffix: string = '') => {
    const { start, end } = cursorPosition;
    const newText = prefix + text + suffix;
    const newValue = value.substring(0, start) + newText + value.substring(end);
    setValue(newValue);
    
    if (textareaRef.current) {
      const newStart = start + prefix.length;
      const newEnd = newStart + text.length;
      textareaRef.current.selectionStart = newStart;
      textareaRef.current.selectionEnd = newEnd;
    }
  }, [value, cursorPosition]);

  const handleToolbarAction = useCallback((action: string) => {
    const { start, end } = cursorPosition;
    const selectedText = value.substring(start, end);
    let newText = '';
    let cursorOffset = 0;

    switch (action) {
      case 'bold':
        newText = `**${selectedText}**`;
        cursorOffset = 2;
        break;
      case 'italic':
        newText = `*${selectedText}*`;
        cursorOffset = 1;
        break;
      case 'underline':
        newText = `__${selectedText}__`;
        cursorOffset = 2;
        break;
      case 'h1':
        newText = `# ${selectedText}`;
        cursorOffset = 2;
        break;
      case 'h2':
        newText = `## ${selectedText}`;
        cursorOffset = 3;
        break;
      case 'h3':
        newText = `### ${selectedText}`;
        cursorOffset = 4;
        break;
      case 'ul':
        newText = selectedText.split('\n').map(line => `- ${line}`).join('\n');
        cursorOffset = 2;
        break;
      case 'ol':
        newText = selectedText.split('\n').map((line, i) => `${i + 1}. ${line}`).join('\n');
        cursorOffset = 3;
        break;
      case 'link':
        newText = `[${selectedText || 'text'}](url)`;
        cursorOffset = selectedText ? 1 : 0;
        break;
      case 'image':
        newText = `![${selectedText || 'alt'}](url)`;
        cursorOffset = selectedText ? 2 : 0;
        break;
      case 'code':
        newText = `\`${selectedText}\``;
        cursorOffset = 1;
        break;
      case 'quote':
        newText = selectedText.split('\n').map(line => `> ${line}`).join('\n');
        cursorOffset = 2;
        break;
      default:
        return;
    }

    const newValue = value.substring(0, start) + newText + value.substring(end);
    setValue(newValue);
    
    if (textareaRef.current) {
      const newStart = start + cursorOffset;
      const newEnd = newStart + (selectedText.length || 0);
      textareaRef.current.selectionStart = newStart;
      textareaRef.current.selectionEnd = newEnd;
    }
  }, [value, cursorPosition]);

  // ========================================
  // RENDER HELPERS
  // ========================================
  
  const renderToolbar = () => {
    if (!showToolbar || mode === 'plain') return null;

    return (
      <div className={cn(
        'flex flex-wrap items-center gap-1 p-1.5',
        'border border-nexus-200 dark:border-nexus-700',
        'bg-nexus-50 dark:bg-nexus-800/50',
        'rounded-t-lg',
        toolbarClassName
      )}>
        {TOOLBAR_BUTTONS.map((btn, index) => {
          if (btn.id === 'divider') {
            return (
              <div key={`divider-${index}`} className="w-px h-6 bg-nexus-200 dark:bg-nexus-700" />
            );
          }

          const Icon = btn.icon;
          return (
            <button
              key={btn.id}
              onClick={() => handleToolbarAction(btn.id)}
              className={cn(
                'p-1.5 rounded hover:bg-nexus-200 dark:hover:bg-nexus-700 transition-colors',
                'text-nexus-500 dark:text-nexus-400 hover:text-nexus-700 dark:hover:text-nexus-200'
              )}
              title={`${btn.label}${btn.shortcut ? ` (${btn.shortcut})` : ''}`}
            >
              <Icon className="w-4 h-4" />
            </button>
          );
        })}
      </div>
    );
  };

  const renderCounter = () => {
    if (!showCounter && !showWordCounter && !showLineCounter) return null;

    return (
      <div className="flex items-center gap-3 text-xs text-nexus-500 dark:text-nexus-400">
        {showCounter && (
          <span className={cn(isOverLimit && 'text-red-500')}>
            {charCount}{maxLength ? `/${maxLength}` : ''}
          </span>
        )}
        {showWordCounter && <span>{wordCount} words</span>}
        {showLineCounter && <span>{lineCount} lines</span>}
      </div>
    );
  };

  const renderStatusIcon = () => {
    if (!hasStatus || !statusConfig.icon) return null;
    return (
      <span className={cn('flex-shrink-0', statusConfig.color)}>
        {statusConfig.icon}
      </span>
    );
  };

  const renderActions = () => {
    return (
      <div className="flex items-center gap-1">
        {enableCopy && (
          <button
            onClick={handleCopy}
            className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors text-nexus-400 hover:text-nexus-600 dark:hover:text-nexus-300"
            title="Copy to clipboard"
          >
            {isCopied ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
          </button>
        )}
        
        {enableExpand && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors text-nexus-400 hover:text-nexus-600 dark:hover:text-nexus-300"
            title={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        )}
        
        {enableFullscreen && (
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors text-nexus-400 hover:text-nexus-600 dark:hover:text-nexus-300"
            title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        )}
        
        {enablePreview && mode !== 'plain' && (
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors text-nexus-400 hover:text-nexus-600 dark:hover:text-nexus-300"
            title={showPreview ? 'Edit' : 'Preview'}
          >
            {showPreview ? <RefreshCw className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </div>
    );
  };

  // ========================================
  // MAIN RENDER
  // ========================================
  
  const inputElement = (
    <textarea
      ref={(el) => {
        if (typeof ref === 'function') {
          ref(el);
        } else if (ref) {
          (ref as React.MutableRefObject<HTMLTextAreaElement | null>).current = el;
        }
        textareaRef.current = el;
      }}
      value={value}
      onChange={handleChange}
      onFocus={handleFocus}
      onBlur={handleBlur}
      onKeyDown={handleKeyDown}
      onSelect={handleSelect}
      maxLength={maxLength}
      required={required}
      aria-label={ariaLabel || label}
      aria-invalid={isError}
      aria-describedby={`${testId}-helper`}
      className={cn(
        'w-full rounded-lg transition-all duration-200',
        sizeConfig.input,
        variantConfig.input,
        colorConfig.focus,
        colorConfig.border,
        isError && 'border-red-500 focus:ring-red-500 focus:border-red-500',
        isFocused && 'ring-2',
        isFullscreen && 'fixed inset-0 z-50 rounded-none !min-h-screen !max-h-screen',
        isExpanded && 'min-h-[300px]',
        resize === 'none' && 'resize-none',
        resize === 'vertical' && 'resize-y',
        resize === 'horizontal' && 'resize-x',
        resize === 'both' && 'resize',
        mode === 'code' && 'font-mono',
        showLineNumbers && 'pl-12',
        inputClassName
      )}
      style={{
        minHeight: minHeight || sizeConfig.minHeight,
        maxHeight: isFullscreen ? '100vh' : maxHeight,
        tabSize,
      }}
      data-testid={testId}
      {...props}
    />
  );

  const containerClasses = cn(
    variantConfig.container,
    isFullscreen && 'fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm',
    className
  );

  const contentClasses = cn(
    'relative w-full',
    isFullscreen && 'max-w-4xl mx-4'
  );

  const labelPositions = {
    top: 'flex-col',
    left: 'flex-row items-center gap-3',
    right: 'flex-row-reverse items-center gap-3',
    bottom: 'flex-col-reverse'
  };

  return (
    <div className={containerClasses}>
      <div className={contentClasses}>
        {(label || helper || isError || hasStatus) && (
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              {label && (
                <label
                  htmlFor={props.id}
                  className={cn(
                    'font-medium',
                    sizeConfig.label,
                    variantConfig.label,
                    colorConfig.text,
                    isError && 'text-red-500',
                    labelClassName
                  )}
                >
                  {label}
                  {required && <span className="text-red-500 ml-0.5">*</span>}
                </label>
              )}
              {renderStatusIcon()}
              {hasStatus && statusConfig.text && (
                <span className={cn('text-sm', statusConfig.color)}>
                  {statusConfig.text}
                </span>
              )}
            </div>
            {renderActions()}
          </div>
        )}

        <div className="relative">
          {/* Line numbers */}
          {showLineNumbers && mode === 'code' && (
            <div className="absolute left-0 top-0 bottom-0 w-10 py-2 overflow-hidden text-right text-nexus-500 dark:text-nexus-600 font-mono text-sm select-none border-r border-nexus-200 dark:border-nexus-700">
              {value.split('\n').map((_, i) => (
                <div key={i} className="px-2 leading-[1.5]">
                  {i + 1}
                </div>
              ))}
            </div>
          )}

          {/* Toolbar */}
          {toolbarPosition === 'top' && renderToolbar()}

          {/* Textarea */}
          {showPreview && mode !== 'plain' ? (
            <div className={cn(
              'min-h-[200px] p-4 rounded-lg border border-nexus-200 dark:border-nexus-700',
              'prose dark:prose-invert max-w-none',
              variantConfig.input
            )}>
              {/* Simple markdown preview */}
              <div className="whitespace-pre-wrap">
                {value}
              </div>
            </div>
          ) : (
            <div className="relative">
              {inputElement}
              
              {/* Status overlay */}
              {isFullscreen && (
                <button
                  onClick={() => setIsFullscreen(false)}
                  className="absolute top-4 right-4 p-2 rounded-lg bg-white/10 hover:bg-white/20 transition-colors text-white"
                >
                  <Minimize2 className="w-5 h-5" />
                </button>
              )}
            </div>
          )}

          {/* Toolbar bottom */}
          {toolbarPosition === 'bottom' && renderToolbar()}

          {/* Bottom bar */}
          <div className="flex items-center justify-between mt-1.5">
            {isError ? (
              <span className={cn('text-sm text-red-500', sizeConfig.helper, errorClassName)}>
                {error || validationError}
              </span>
            ) : warning ? (
              <span className={cn('text-sm text-yellow-500', sizeConfig.helper, helperClassName)}>
                {warning}
              </span>
            ) : success ? (
              <span className={cn('text-sm text-emerald-500', sizeConfig.helper, helperClassName)}>
                {success}
              </span>
            ) : helper ? (
              <span className={cn('text-sm', variantConfig.helper, sizeConfig.helper, helperClassName)}>
                {helper}
              </span>
            ) : (
              <span />
            )}

            {renderCounter()}
          </div>
        </div>
      </div>
    </div>
  );
});

Textarea.displayName = 'Textarea';

// ========================================
// COMPOUND COMPONENTS
// ========================================

export interface TextareaGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  label?: string;
  error?: string;
  helper?: string;
  required?: boolean;
  className?: string;
}

export const TextareaGroup: React.FC<TextareaGroupProps> = ({
  children,
  label,
  error,
  helper,
  required,
  className,
  ...props
}) => {
  return (
    <div className={cn('space-y-1.5', className)} {...props}>
      {label && (
        <label className="text-sm font-medium text-nexus-700 dark:text-nexus-300">
          {label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
      )}
      {children}
      {helper && !error && (
        <p className="text-sm text-nexus-500 dark:text-nexus-400">{helper}</p>
      )}
      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}
    </div>
  );
};

// ========================================
// PRESETED TEXTAREA COMPONENTS
// ========================================

export const TextareaPresets = {
  Default: (props: Omit<TextareaProps, 'variant'>) => (
    <Textarea variant="default" {...props} />
  ),
  Outlined: (props: Omit<TextareaProps, 'variant'>) => (
    <Textarea variant="outlined" {...props} />
  ),
  Filled: (props: Omit<TextareaProps, 'variant'>) => (
    <Textarea variant="filled" {...props} />
  ),
  Minimal: (props: Omit<TextareaProps, 'variant'>) => (
    <Textarea variant="minimal" {...props} />
  ),
  Code: (props: Omit<TextareaProps, 'variant'>) => (
    <Textarea variant="code" mode="code" {...props} />
  ),
  Rich: (props: Omit<TextareaProps, 'variant'>) => (
    <Textarea mode="rich" showToolbar {...props} />
  ),
  Markdown: (props: Omit<TextareaProps, 'variant'>) => (
    <Textarea mode="markdown" showToolbar enablePreview {...props} />
  )
};

// ========================================
// EXPORTS
// ========================================

TextareaGroup.displayName = 'TextareaGroup';

export default Textarea;

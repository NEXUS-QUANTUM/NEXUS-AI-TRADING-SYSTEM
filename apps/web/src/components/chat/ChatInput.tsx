/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { cn } from '@/utils/helpers';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import {
  Send,
  Paperclip,
  Image,
  Smile,
  Mic,
  X,
  Loader2,
  StopCircle,
  Bold,
  Italic,
  Underline,
  Link,
  Code,
  Quote,
  List,
  ListOrdered,
  AlignLeft,
  AlignCenter,
  AlignRight,
} from 'lucide-react';
import { EmojiPicker } from './EmojiPicker';
import { FileUpload } from './FileUpload';
import { VoiceRecorder } from './VoiceRecorder';

// ============================================
// TYPES
// ============================================

interface ChatInputProps {
  onSendMessage: (message: string, attachments?: File[]) => void;
  onTyping?: (isTyping: boolean) => void;
  onStartRecording?: () => void;
  onStopRecording?: (blob: Blob) => void;
  placeholder?: string;
  disabled?: boolean;
  isLoading?: boolean;
  isRecording?: boolean;
  showEmojiPicker?: boolean;
  showFileUpload?: boolean;
  showImageUpload?: boolean;
  showVoiceRecorder?: boolean;
  showFormatting?: boolean;
  maxLength?: number;
  rows?: number;
  className?: string;
  value?: string;
  onChange?: (value: string) => void;
  onFocus?: () => void;
  onBlur?: () => void;
}

// ============================================
// CONSTANTES
// ============================================

const MAX_ROWS = 8;
const DEFAULT_ROWS = 1;
const TYPING_TIMEOUT = 2000;

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

export function ChatInput({
  onSendMessage,
  onTyping,
  onStartRecording,
  onStopRecording,
  placeholder = 'Écrivez votre message...',
  disabled = false,
  isLoading = false,
  isRecording = false,
  showEmojiPicker = true,
  showFileUpload = true,
  showImageUpload = true,
  showVoiceRecorder = true,
  showFormatting = false,
  maxLength = 5000,
  rows = DEFAULT_ROWS,
  className = '',
  value: externalValue,
  onChange: externalOnChange,
  onFocus,
  onBlur,
}: ChatInputProps) {
  // ============================================
  // RÉFÉRENCES
  // ============================================
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // ============================================
  // ÉTATS
  // ============================================
  const [internalValue, setInternalValue] = useState('');
  const [attachments, setAttachments] = useState<File[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [showEmojiPickerState, setShowEmojiPickerState] = useState(false);
  const [showFileUploadState, setShowFileUploadState] = useState(false);
  const [showFormattingState, setShowFormattingState] = useState(false);
  const [cursorPosition, setCursorPosition] = useState(0);

  const value = externalValue !== undefined ? externalValue : internalValue;
  const onChange = externalOnChange || setInternalValue;

  // ============================================
  // GESTION DU TEXTE
  // ============================================

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    onChange(newValue);
    setCursorPosition(e.target.selectionStart);

    // Gestion du typing
    if (!isTyping) {
      setIsTyping(true);
      onTyping?.(true);
    }

    // Reset du timeout de typing
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    typingTimeoutRef.current = setTimeout(() => {
      setIsTyping(false);
      onTyping?.(false);
    }, TYPING_TIMEOUT);

    // Ajustement automatique de la hauteur
    autoResizeTextarea();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Envoi avec Ctrl+Enter ou Shift+Enter
    if ((e.key === 'Enter' && (e.ctrlKey || e.metaKey)) ||
        (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey)) {
      e.preventDefault();
      handleSend();
    }

    // Nouvelle ligne avec Shift+Enter
    if (e.key === 'Enter' && e.shiftKey) {
      // Permet le saut de ligne
    }

    // Tabulation
    if (e.key === 'Tab') {
      e.preventDefault();
      const textarea = e.currentTarget;
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const newValue = value.substring(0, start) + '  ' + value.substring(end);
      onChange(newValue);
      textarea.selectionStart = textarea.selectionEnd = start + 2;
      autoResizeTextarea();
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    // Vérifier si des images ont été collées
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        const file = item.getAsFile();
        if (file) {
          handleFileUpload([file]);
        }
        break;
      }
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLTextAreaElement>) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileUpload(files);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLTextAreaElement>) => {
    e.preventDefault();
    e.currentTarget.classList.add('border-blue-500', 'bg-blue-50/10');
  };

  const handleDragLeave = (e: React.DragEvent<HTMLTextAreaElement>) => {
    e.preventDefault();
    e.currentTarget.classList.remove('border-blue-500', 'bg-blue-50/10');
  };

  // ============================================
  // AUTO-RESIZE
  // ============================================

  const autoResizeTextarea = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = 'auto';
    const newHeight = Math.min(
      textarea.scrollHeight,
      textarea.scrollHeight * MAX_ROWS
    );
    textarea.style.height = `${newHeight}px`;
  }, []);

  useEffect(() => {
    autoResizeTextarea();
  }, [value, autoResizeTextarea]);

  // ============================================
  // ENVOI DU MESSAGE
  // ============================================

  const handleSend = () => {
    const trimmedValue = value.trim();
    if (!trimmedValue && attachments.length === 0) return;

    onSendMessage(trimmedValue, attachments.length > 0 ? attachments : undefined);
    onChange('');
    setAttachments([]);
    setIsTyping(false);
    onTyping?.(false);
    setShowEmojiPickerState(false);
    setShowFileUploadState(false);

    // Réinitialiser la hauteur
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
    }

    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
  };

  // ============================================
  // GESTION DES FICHIERS
  // ============================================

  const handleFileUpload = (files: File[]) => {
    const validFiles = files.filter((file) => {
      const isValidSize = file.size <= 10 * 1024 * 1024; // 10MB
      if (!isValidSize) {
        console.warn(`Fichier ${file.name} trop volumineux (max 10MB)`);
        return false;
      }
      return true;
    });

    setAttachments((prev) => [...prev, ...validFiles]);

    // Auto-focus sur le textarea
    textareaRef.current?.focus();
  };

  const handleRemoveAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  // ============================================
  // INSÉRER DES ÉMOJIS
  // ============================================

  const handleEmojiSelect = (emoji: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const newValue = value.substring(0, start) + emoji + value.substring(end);
    onChange(newValue);

    // Placer le curseur après l'emoji
    const newCursorPos = start + emoji.length;
    setTimeout(() => {
      textarea.focus();
      textarea.selectionStart = textarea.selectionEnd = newCursorPos;
    }, 0);

    setShowEmojiPickerState(false);
  };

  // ============================================
  // INSÉRER DU FORMATAGE
  // ============================================

  const insertFormatting = (format: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = value.substring(start, end);

    let formattedText = '';
    let cursorOffset = 0;

    switch (format) {
      case 'bold':
        formattedText = `**${selectedText || 'texte en gras'}**`;
        cursorOffset = 2;
        break;
      case 'italic':
        formattedText = `*${selectedText || 'texte en italique'}*`;
        cursorOffset = 1;
        break;
      case 'underline':
        formattedText = `__${selectedText || 'texte souligné'}__`;
        cursorOffset = 2;
        break;
      case 'strike':
        formattedText = `~~${selectedText || 'texte barré'}~~`;
        cursorOffset = 2;
        break;
      case 'link':
        formattedText = `[${selectedText || 'texte du lien'}](url)`;
        cursorOffset = 1;
        break;
      case 'code':
        formattedText = `\`${selectedText || 'code'}\``;
        cursorOffset = 1;
        break;
      case 'codeblock':
        formattedText = `\`\`\`\n${selectedText || 'code'}\n\`\`\``;
        cursorOffset = 4;
        break;
      case 'quote':
        formattedText = `> ${selectedText || 'citation'}`;
        cursorOffset = 2;
        break;
      case 'list':
        formattedText = `- ${selectedText || 'élément de liste'}`;
        cursorOffset = 2;
        break;
      case 'listordered':
        formattedText = `1. ${selectedText || 'élément de liste'}`;
        cursorOffset = 3;
        break;
      default:
        return;
    }

    const newValue = value.substring(0, start) + formattedText + value.substring(end);
    onChange(newValue);

    const newCursorPos = start + (selectedText ? formattedText.length : cursorOffset + (selectedText || '').length);
    setTimeout(() => {
      textarea.focus();
      textarea.selectionStart = textarea.selectionEnd = newCursorPos;
    }, 0);
  };

  // ============================================
  // NETTOYAGE
  // ============================================

  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
    };
  }, []);

  // ============================================
  // RENDU
  // ============================================

  const hasAttachments = attachments.length > 0;
  const hasContent = value.trim().length > 0 || hasAttachments;
  const isSendDisabled = disabled || isLoading || (!hasContent);

  return (
    <div className={cn('relative', className)}>
      {/* Barre d'outils */}
      <div className="flex items-center gap-1 px-3 py-1.5 border-b border-gray-200 dark:border-gray-700">
        {/* Émojis */}
        {showEmojiPicker && (
          <div className="relative">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => setShowEmojiPickerState(!showEmojiPickerState)}
            >
              <Smile className="h-4 w-4" />
            </Button>
            {showEmojiPickerState && (
              <div className="absolute bottom-full left-0 mb-2 z-50">
                <EmojiPicker onSelect={handleEmojiSelect} />
              </div>
            )}
          </div>
        )}

        {/* Pièce jointe */}
        {showFileUpload && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={() => fileInputRef.current?.click()}
          >
            <Paperclip className="h-4 w-4" />
          </Button>
        )}

        {/* Image */}
        {showImageUpload && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={() => imageInputRef.current?.click()}
          >
            <Image className="h-4 w-4" />
          </Button>
        )}

        {/* Micro */}
        {showVoiceRecorder && (
          <VoiceRecorder
            onStartRecording={onStartRecording}
            onStopRecording={onStopRecording}
            isRecording={isRecording}
          />
        )}

        {/* Formatage */}
        {showFormatting && (
          <>
            <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 mx-1" />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => insertFormatting('bold')}
              title="Gras"
            >
              <Bold className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => insertFormatting('italic')}
              title="Italique"
            >
              <Italic className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => insertFormatting('underline')}
              title="Souligné"
            >
              <Underline className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => insertFormatting('link')}
              title="Lien"
            >
              <Link className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => insertFormatting('code')}
              title="Code"
            >
              <Code className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => insertFormatting('quote')}
              title="Citation"
            >
              <Quote className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => insertFormatting('list')}
              title="Liste"
            >
              <List className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => insertFormatting('listordered')}
              title="Liste ordonnée"
            >
              <ListOrdered className="h-4 w-4" />
            </Button>
          </>
        )}

        <div className="flex-1" />

        {/* Compteur de caractères */}
        {maxLength > 0 && (
          <span className={cn(
            'text-xs',
            value.length > maxLength * 0.9
              ? 'text-red-500'
              : 'text-gray-400'
          )}>
            {value.length}/{maxLength}
          </span>
        )}
      </div>

      {/* Zone de texte */}
      <div className="relative">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onFocus={onFocus}
          onBlur={onBlur}
          placeholder={placeholder}
          disabled={disabled}
          maxLength={maxLength}
          rows={rows}
          className={cn(
            'w-full resize-none bg-transparent px-4 py-2.5 text-sm',
            'outline-none placeholder:text-gray-400 dark:placeholder:text-gray-500',
            'scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600',
            'transition-all duration-200',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
          style={{
            minHeight: `${rows * 24 + 20}px`,
            maxHeight: `${MAX_ROWS * 24 + 20}px`,
          }}
        />
      </div>

      {/* Inputs cachés pour les fichiers */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => {
          const files = Array.from(e.target.files || []);
          if (files.length > 0) {
            handleFileUpload(files);
          }
          e.target.value = '';
        }}
        accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.csv,.json,.xml,.zip,.rar"
      />

      <input
        ref={imageInputRef}
        type="file"
        multiple
        className="hidden"
        accept="image/*"
        onChange={(e) => {
          const files = Array.from(e.target.files || []);
          if (files.length > 0) {
            handleFileUpload(files);
          }
          e.target.value = '';
        }}
      />

      {/* Pièces jointes */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 px-3 pb-2">
          {attachments.map((file, index) => (
            <div
              key={index}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-800 text-sm"
            >
              {file.type.startsWith('image/') ? (
                <Image className="h-4 w-4 text-gray-500" />
              ) : (
                <Paperclip className="h-4 w-4 text-gray-500" />
              )}
              <span className="truncate max-w-[150px]">{file.name}</span>
              <span className="text-xs text-gray-400">
                {(file.size / 1024).toFixed(0)} KB
              </span>
              <button
                type="button"
                className="text-gray-400 hover:text-red-500 transition-colors"
                onClick={() => handleRemoveAttachment(index)}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Bouton d'envoi */}
      <div className="absolute right-2 bottom-2">
        <Button
          type="button"
          size="sm"
          className={cn(
            'h-9 w-9 rounded-full transition-all duration-200',
            isSendDisabled
              ? 'opacity-50 cursor-not-allowed'
              : 'hover:scale-105'
          )}
          onClick={handleSend}
          disabled={isSendDisabled}
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : isRecording ? (
            <StopCircle className="h-4 w-4" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </div>
    </div>
  );
}

/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import { cn } from '@/utils/helpers';
import { Avatar, AvatarImage, AvatarFallback } from './Avatar';
import { Button } from './Button';
import { Upload, X, Loader2, Camera, Trash2 } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './Tooltip';

// ============================================
// TYPES
// ============================================

export interface AvatarUploadProps {
  src?: string;
  alt?: string;
  fallback?: string;
  onUpload?: (file: File) => void | Promise<void>;
  onRemove?: () => void | Promise<void>;
  onError?: (error: Error) => void;
  isLoading?: boolean;
  isRemoving?: boolean;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl';
  className?: string;
  accept?: string;
  maxSize?: number; // en bytes
  allowedTypes?: string[];
  disabled?: boolean;
  showRemoveButton?: boolean;
  showUploadButton?: boolean;
  showEditOverlay?: boolean;
  uploadLabel?: string;
  removeLabel?: string;
  errorMessage?: string;
  successMessage?: string;
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}

// ============================================
// CONSTANTES
// ============================================

const SIZE_CLASSES = {
  xs: 'h-8 w-8',
  sm: 'h-10 w-10',
  md: 'h-16 w-16',
  lg: 'h-20 w-20',
  xl: 'h-24 w-24',
  '2xl': 'h-32 w-32',
};

const ICON_SIZE_CLASSES = {
  xs: 'h-3 w-3',
  sm: 'h-4 w-4',
  md: 'h-6 w-6',
  lg: 'h-8 w-8',
  xl: 'h-10 w-10',
  '2xl': 'h-12 w-12',
};

const DEFAULT_ACCEPT = 'image/*';
const DEFAULT_MAX_SIZE = 5 * 1024 * 1024; // 5MB
const DEFAULT_ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'];

// ============================================
// COMPOSANT
// ============================================

export function AvatarUpload({
  src,
  alt = 'Avatar',
  fallback,
  onUpload,
  onRemove,
  onError,
  isLoading = false,
  isRemoving = false,
  size = 'md',
  className,
  accept = DEFAULT_ACCEPT,
  maxSize = DEFAULT_MAX_SIZE,
  allowedTypes = DEFAULT_ALLOWED_TYPES,
  disabled = false,
  showRemoveButton = true,
  showUploadButton = true,
  showEditOverlay = true,
  uploadLabel = 'Changer la photo',
  removeLabel = 'Supprimer',
  errorMessage = 'Erreur lors du téléchargement',
  successMessage = 'Photo mise à jour avec succès',
  onSuccess,
}: AvatarUploadProps) {
  // ============================================
  // RÉFÉRENCES
  // ============================================
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // ============================================
  // ÉTATS
  // ============================================
  const [isHovered, setIsHovered] = React.useState(false);
  const [localSrc, setLocalSrc] = React.useState<string | undefined>(src);
  const [isUploading, setIsUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [success, setSuccess] = React.useState<string | null>(null);

  // ============================================
  // EFFETS
  // ============================================
  React.useEffect(() => {
    if (src !== localSrc) {
      setLocalSrc(src);
    }
  }, [src]);

  // ============================================
  // FONCTIONS
  // ============================================

  const resetStates = () => {
    setError(null);
    setSuccess(null);
  };

  const validateFile = (file: File): boolean => {
    // Vérifier le type
    if (!allowedTypes.includes(file.type)) {
      setError(`Format non supporté. Types acceptés: ${allowedTypes.join(', ')}`);
      onError?.(new Error(`Format non supporté: ${file.type}`));
      return false;
    }

    // Vérifier la taille
    if (file.size > maxSize) {
      setError(`Fichier trop volumineux. Taille max: ${maxSize / 1024 / 1024}MB`);
      onError?.(new Error(`Fichier trop volumineux: ${file.size} bytes`));
      return false;
    }

    return true;
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    resetStates();

    if (!validateFile(file)) {
      event.target.value = '';
      return;
    }

    try {
      setIsUploading(true);
      setError(null);

      // Créer une URL pour l'aperçu
      const objectUrl = URL.createObjectURL(file);
      setLocalSrc(objectUrl);

      // Appeler le callback d'upload
      await onUpload?.(file);

      setSuccess(successMessage);
      onSuccess?.();

      // Nettoyer l'URL après un délai
      setTimeout(() => {
        URL.revokeObjectURL(objectUrl);
      }, 1000);
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Erreur lors du téléchargement');
      setError(error.message);
      onError?.(error);
      // Restaurer l'ancienne image
      setLocalSrc(src);
    } finally {
      setIsUploading(false);
      event.target.value = '';
    }
  };

  const handleRemove = async () => {
    resetStates();

    try {
      setLocalSrc(undefined);
      await onRemove?.();
      setSuccess('Photo supprimée avec succès');
      onSuccess?.();
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Erreur lors de la suppression');
      setError(error.message);
      onError?.(error);
      setLocalSrc(src);
    }
  };

  const handleClick = () => {
    if (disabled || isLoading || isUploading) return;
    fileInputRef.current?.click();
  };

  // ============================================
  // RENDU
  // ============================================

  const sizeClass = SIZE_CLASSES[size];
  const iconSize = ICON_SIZE_CLASSES[size];
  const hasImage = !!localSrc;
  const isProcessing = isLoading || isUploading || isRemoving;
  const showOverlay = isHovered && !isProcessing && !disabled && showEditOverlay;

  return (
    <div
      className={cn('relative inline-block', className)}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Avatar */}
      <div
        className={cn(
          'relative rounded-full transition-all duration-200',
          'ring-2 ring-transparent',
          isHovered && !disabled && 'ring-blue-500 ring-offset-2',
          disabled && 'opacity-60 cursor-not-allowed',
          isProcessing && 'opacity-70'
        )}
      >
        <Avatar className={cn(sizeClass, 'cursor-pointer')} onClick={handleClick}>
          <AvatarImage src={localSrc} alt={alt} />
          <AvatarFallback>{fallback || alt?.charAt(0)?.toUpperCase() || '?'}</AvatarFallback>
        </Avatar>

        {/* Indicateur de chargement */}
        {isProcessing && (
          <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black/40">
            <Loader2 className={cn('animate-spin text-white', iconSize)} />
          </div>
        )}

        {/* Overlay d'édition */}
        {showOverlay && (
          <div
            className="absolute inset-0 flex items-center justify-center rounded-full bg-black/40 transition-opacity duration-200"
            onClick={handleClick}
          >
            <Camera className={cn('text-white', iconSize)} />
          </div>
        )}

        {/* Status messages */}
        {error && (
          <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs text-red-500">
            {error}
          </div>
        )}
        {success && (
          <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 whitespace-nowrap text-xs text-green-500">
            {success}
          </div>
        )}
      </div>

      {/* Input caché */}
      <input
        ref={fileInputRef}
        type="file"
        accept={accept}
        onChange={handleFileChange}
        disabled={disabled || isProcessing}
        className="hidden"
        aria-label="Télécharger un avatar"
      />

      {/* Boutons d'actions */}
      {showUploadButton && !disabled && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className={cn(
                  'absolute -bottom-2 -right-2 h-6 w-6 rounded-full p-0',
                  'border-gray-200 dark:border-gray-700',
                  'bg-white dark:bg-gray-800',
                  'hover:bg-gray-100 dark:hover:bg-gray-700',
                  'transition-all duration-200',
                  isProcessing && 'opacity-50 cursor-not-allowed'
                )}
                onClick={handleClick}
                disabled={isProcessing}
              >
                <Upload className="h-3 w-3" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p>{uploadLabel}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}

      {/* Bouton de suppression */}
      {showRemoveButton && hasImage && !disabled && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                className={cn(
                  'absolute -bottom-2 -right-2 h-6 w-6 rounded-full p-0',
                  'transition-all duration-200',
                  isProcessing && 'opacity-50 cursor-not-allowed'
                )}
                onClick={handleRemove}
                disabled={isProcessing}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p>{removeLabel}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </div>
  );
}

// ============================================
// EXPORTATIONS
// ============================================

export default AvatarUpload;

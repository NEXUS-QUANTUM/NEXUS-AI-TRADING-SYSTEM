// apps/web/src/components/forms/fields/ImageField.tsx
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
  ChangeEvent,
  DragEvent,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  PhotoIcon,
  CameraIcon,
  CloudArrowUpIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ArrowPathIcon,
  EyeIcon,
  EyeSlashIcon,
  TrashIcon,
  PencilIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  PlusIcon,
  MinusIcon,
  RotateCwIcon,
  RotateCcwIcon,
  CropIcon,
  AdjustmentsHorizontalIcon,
  RectangleGroupIcon,
  Squares2X2Icon,
  ListBulletIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
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
import { Progress } from '@/components/common/Progress';
import { Slider } from '@/components/common/Slider';
import { Tooltip } from '@/components/common/Tooltip';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type ImageStatus = 'idle' | 'uploading' | 'success' | 'error' | 'cancelled';
export type ImageFit = 'cover' | 'contain' | 'fill' | 'none' | 'scale-down';
export type ImagePosition = 'center' | 'top' | 'bottom' | 'left' | 'right' | 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';

export interface UploadImage {
  /** Identifiant unique */
  id: string;
  /** Nom du fichier */
  name: string;
  /** Taille du fichier (bytes) */
  size: number;
  /** Type MIME */
  type: string;
  /** Statut */
  status: ImageStatus;
  /** Progression (0-100) */
  progress: number;
  /** URL de prévisualisation */
  previewUrl: string;
  /** Fichier brut */
  file?: File;
  /** Message d'erreur */
  error?: string;
  /** Dimensions */
  dimensions?: { width: number; height: number };
  /** Métadonnées */
  metadata?: {
    alt?: string;
    title?: string;
    caption?: string;
  };
  /** Date d'upload */
  uploadedAt?: Date;
}

export interface ImageFieldProps {
  // --- Contrôle ---
  /** Valeur du champ */
  value?: UploadImage[] | UploadImage | null;
  /** Valeur par défaut */
  defaultValue?: UploadImage[] | UploadImage | null;
  /** Callback de changement */
  onChange?: (value: UploadImage[] | UploadImage | null) => void;
  /** Callback de blur */
  onBlur?: () => void;
  /** Callback de focus */
  onFocus?: () => void;
  /** Callback de validation */
  onValidate?: (valid: boolean, value: UploadImage[] | UploadImage | null) => void;

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
  /** Afficher la prévisualisation */
  showPreview?: boolean;
  /** Afficher la progression */
  showProgress?: boolean;
  /** Afficher les contrôles */
  showControls?: boolean;
  /** Afficher les informations */
  showInfo?: boolean;
  /** Mode d'affichage */
  displayMode?: 'grid' | 'list' | 'carousel';

  // --- Comportement ---
  /** Mode multi-images */
  multi?: boolean;
  /** Nombre maximum d'images */
  maxImages?: number;
  /** Taille maximale (bytes) */
  maxSize?: number;
  /** Largeur minimale */
  minWidth?: number;
  /** Largeur maximale */
  maxWidth?: number;
  /** Hauteur minimale */
  minHeight?: number;
  /** Hauteur maximale */
  maxHeight?: number;
  /** Formats acceptés */
  accept?: string[];
  /** Ratio d'aspect (ex: '16:9', '4:3', '1:1') */
  aspectRatio?: string;
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Désactiver le drag & drop */
  disableDragDrop?: boolean;
  /** Désactiver le recadrage */
  disableCrop?: boolean;
  /** Désactiver le redimensionnement */
  disableResize?: boolean;
  /** Désactiver la rotation */
  disableRotate?: boolean;
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
  /** Fonction de validation personnalisée */
  customValidate?: (images: UploadImage[] | UploadImage | null) => boolean | string;
  /** Fonction de formatage personnalisée */
  customFormat?: (file: File) => UploadImage;
  /** Ref */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const ACCEPT_IMAGES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml', 'image/bmp', 'image/tiff'];
const DEFAULT_MAX_SIZE = 5 * 1024 * 1024; // 5MB
const DEFAULT_MAX_IMAGES = 10;
const DEFAULT_IMAGE_FIT: ImageFit = 'cover';

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const ImageField = forwardRef<HTMLInputElement, ImageFieldProps>(
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
      placeholder = 'Déposez vos images ici ou cliquez pour parcourir',
      description,
      error,
      success,
      info,
      showPreview = true,
      showProgress = true,
      showControls = true,
      showInfo = true,
      displayMode = 'grid',

      // Comportement
      multi = false,
      maxImages = DEFAULT_MAX_IMAGES,
      maxSize = DEFAULT_MAX_SIZE,
      minWidth,
      maxWidth,
      minHeight,
      maxHeight,
      accept = ACCEPT_IMAGES,
      aspectRatio,
      disabled = false,
      required = false,
      disableDragDrop = false,
      disableCrop = false,
      disableResize = false,
      disableRotate = false,
      disableRealtimeValidation = false,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,
      name,

      // Avancé
      customValidate,
      customFormat,
      inputRef,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const inputRefInternal = useRef<HTMLInputElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const dropAreaRef = useRef<HTMLDivElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const prevValueRef = useRef<UploadImage[] | null>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState<UploadImage[] | null>(
      defaultValue ? (Array.isArray(defaultValue) ? defaultValue : [defaultValue]) : null
    );
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');
    const [isDragging, setIsDragging] = useState(false);
    const [uploadingImages, setUploadingImages] = useState<Set<string>>(new Set());
    const [selectedImage, setSelectedImage] = useState<string | null>(null);
    const [viewMode, setViewMode] = useState<'grid' | 'list' | 'carousel'>(displayMode);
    const [editingImage, setEditingImage] = useState<string | null>(null);
    const [cropMode, setCropMode] = useState(false);
    const [cropArea, setCropArea] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
    const [rotation, setRotation] = useState(0);
    const [zoom, setZoom] = useState(100);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined 
      ? (Array.isArray(externalValue) ? externalValue : externalValue ? [externalValue] : null)
      : internalValue;
    const isControlled = externalValue !== undefined;
    const imageCount = value?.length || 0;
    const isMaxImagesReached = multi && imageCount >= maxImages;

    // ========================================================================
    // UTILITAIRES
    // ========================================================================

    const formatFileSize = useCallback((bytes: number): string => {
      if (bytes === 0) return '0 B';
      const units = ['B', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(1024));
      const size = bytes / Math.pow(1024, i);
      return `${size.toFixed(1)} ${units[i]}`;
    }, []);

    const generateId = useCallback(() => {
      return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    }, []);

    const getImageDimensions = useCallback((file: File): Promise<{ width: number; height: number }> => {
      return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
          resolve({ width: img.width, height: img.height });
          URL.revokeObjectURL(img.src);
        };
        img.onerror = reject;
        img.src = URL.createObjectURL(file);
      });
    }, []);

    const createUploadImage = useCallback(async (file: File): Promise<UploadImage> => {
      const previewUrl = URL.createObjectURL(file);
      const dimensions = await getImageDimensions(file);
      
      return {
        id: generateId(),
        name: file.name,
        size: file.size,
        type: file.type,
        status: 'idle',
        progress: 0,
        previewUrl,
        file,
        dimensions,
        uploadedAt: new Date(),
        metadata: {},
      };
    }, [generateId, getImageDimensions]);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateImages = useCallback((images: UploadImage[] | null): { valid: boolean; message: string } => {
      if (customValidate) {
        const result = customValidate(images);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (!images || images.length === 0) {
        if (required) {
          return { valid: false, message: 'Veuillez sélectionner au moins une image' };
        }
        return { valid: true, message: '' };
      }

      // Vérifier le nombre maximum
      if (multi && images.length > maxImages) {
        return { valid: false, message: `Maximum ${maxImages} image${maxImages > 1 ? 's' : ''} autorisé${maxImages > 1 ? 's' : ''}` };
      }

      // Vérifier chaque image
      for (const image of images) {
        // Vérifier la taille
        if (image.size > maxSize) {
          return { valid: false, message: `L'image "${image.name}" dépasse la taille maximale (${formatFileSize(maxSize)})` };
        }

        // Vérifier le type
        if (!accept.includes(image.type)) {
          return { valid: false, message: `L'image "${image.name}" n'est pas d'un format accepté` };
        }

        // Vérifier les dimensions
        if (image.dimensions) {
          if (minWidth && image.dimensions.width < minWidth) {
            return { valid: false, message: `L'image "${image.name}" est trop étroite (min ${minWidth}px)` };
          }
          if (maxWidth && image.dimensions.width > maxWidth) {
            return { valid: false, message: `L'image "${image.name}" est trop large (max ${maxWidth}px)` };
          }
          if (minHeight && image.dimensions.height < minHeight) {
            return { valid: false, message: `L'image "${image.name}" est trop petite (min ${minHeight}px)` };
          }
          if (maxHeight && image.dimensions.height > maxHeight) {
            return { valid: false, message: `L'image "${image.name}" est trop grande (max ${maxHeight}px)` };
          }

          // Vérifier le ratio
          if (aspectRatio) {
            const [ratioW, ratioH] = aspectRatio.split(':').map(Number);
            const imageRatio = image.dimensions.width / image.dimensions.height;
            const targetRatio = ratioW / ratioH;
            if (Math.abs(imageRatio - targetRatio) > 0.01) {
              return { valid: false, message: `L'image "${image.name}" ne respecte pas le ratio ${aspectRatio}` };
            }
          }
        }
      }

      return { valid: true, message: '' };
    }, [
      customValidate,
      required,
      multi,
      maxImages,
      maxSize,
      accept,
      minWidth,
      maxWidth,
      minHeight,
      maxHeight,
      aspectRatio,
      formatFileSize,
    ]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((images: UploadImage[] | null) => {
      const validation = validateImages(images);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, images);
      }

      const finalValue = multi ? images : (images && images.length > 0 ? images[0] : null);

      if (isControlled) {
        if (onChange) onChange(finalValue);
      } else {
        setInternalValue(images);
        if (onChange) onChange(finalValue);
      }

      if (debug) {
        console.log('ImageField update:', { images, count: images?.length || 0, isValid: validation.valid });
      }
    }, [
      validateImages,
      multi,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      debug,
    ]);

    // ========================================================================
    // TRAITEMENT DES IMAGES
    // ========================================================================

    const processFiles = useCallback(async (fileList: FileList | File[]) => {
      const files = Array.from(fileList);
      
      // Vérifier le nombre maximum
      if (multi && imageCount + files.length > maxImages) {
        toast({
          title: 'Limite d\'images atteinte',
          description: `Maximum ${maxImages} image${maxImages > 1 ? 's' : ''} autorisé${maxImages > 1 ? 's' : ''}`,
          variant: 'destructive',
        });
        return;
      }

      const newImages: UploadImage[] = [];
      const errors: string[] = [];

      for (const file of files) {
        try {
          // Vérifier le type
          if (!accept.includes(file.type)) {
            errors.push(`"${file.name}" n'est pas d'un format accepté`);
            continue;
          }

          // Vérifier la taille
          if (file.size > maxSize) {
            errors.push(`"${file.name}" dépasse la taille maximale (${formatFileSize(maxSize)})`);
            continue;
          }

          const uploadImage = customFormat 
            ? await customFormat(file) 
            : await createUploadImage(file);
          
          newImages.push(uploadImage);
          
          // Simuler l'upload
          if (showProgress) {
            simulateUpload(uploadImage.id);
          }
        } catch (error) {
          errors.push(`"${file.name}" - Erreur de traitement`);
          if (debug) console.error('Erreur de traitement:', error);
        }
      }

      if (errors.length > 0) {
        toast({
          title: 'Erreurs de validation',
          description: errors.join('\n'),
          variant: 'destructive',
          duration: 5000,
        });
      }

      if (newImages.length > 0) {
        const currentImages = value || [];
        const updatedImages = multi ? [...currentImages, ...newImages] : newImages;
        updateValue(updatedImages);
      }
    }, [
      multi,
      maxImages,
      imageCount,
      accept,
      maxSize,
      formatFileSize,
      showProgress,
      customFormat,
      createUploadImage,
      value,
      updateValue,
      toast,
      debug,
    ]);

    // ========================================================================
    // SIMULATION D'UPLOAD
    // ========================================================================

    const simulateUpload = useCallback((imageId: string) => {
      setUploadingImages(prev => new Set([...prev, imageId]));
      
      let progress = 0;
      const interval = setInterval(() => {
        progress += Math.random() * 15 + 5;
        if (progress >= 100) {
          progress = 100;
          clearInterval(interval);
          updateImageStatus(imageId, 'success', 100);
          setUploadingImages(prev => {
            const next = new Set(prev);
            next.delete(imageId);
            return next;
          });
        } else {
          updateImageProgress(imageId, Math.round(Math.min(100, progress)));
        }
      }, 200);
    }, []);

    const updateImageProgress = useCallback((imageId: string, progress: number) => {
      if (!value) return;
      const updated = value.map(img => 
        img.id === imageId ? { ...img, progress, status: 'uploading' as ImageStatus } : img
      );
      updateValue(updated);
    }, [value, updateValue]);

    const updateImageStatus = useCallback((imageId: string, status: ImageStatus, progress: number) => {
      if (!value) return;
      const updated = value.map(img => 
        img.id === imageId ? { ...img, status, progress } : img
      );
      updateValue(updated);
    }, [value, updateValue]);

    // ========================================================================
    // GESTION DES IMAGES
    // ========================================================================

    const handleRemoveImage = useCallback((imageId: string) => {
      if (!value) return;
      const updated = value.filter(img => img.id !== imageId);
      // Nettoyer l'URL de prévisualisation
      const removed = value.find(img => img.id === imageId);
      if (removed?.previewUrl) {
        URL.revokeObjectURL(removed.previewUrl);
      }
      updateValue(updated.length > 0 ? updated : null);
      
      toast({
        title: 'Image supprimée',
        description: 'L\'image a été retirée de la liste',
        duration: 2000,
      });
    }, [value, updateValue, toast]);

    const handleRemoveAll = useCallback(() => {
      if (value) {
        value.forEach(img => {
          if (img.previewUrl) URL.revokeObjectURL(img.previewUrl);
        });
      }
      updateValue(null);
      toast({
        title: 'Images supprimées',
        description: 'Toutes les images ont été retirées',
        duration: 2000,
      });
    }, [value, updateValue, toast]);

    // ========================================================================
    // DRAG & DROP
    // ========================================================================

    const handleDragEnter = useCallback((e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      if (!disableDragDrop && !disabled) {
        setIsDragging(true);
      }
    }, [disableDragDrop, disabled]);

    const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
    }, []);

    const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
    }, []);

    const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      
      if (disableDragDrop || disabled) return;
      
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        const imageFiles = Array.from(files).filter(f => f.type.startsWith('image/'));
        if (imageFiles.length > 0) {
          processFiles(imageFiles);
        } else {
          toast({
            title: 'Fichiers non supportés',
            description: 'Veuillez déposer uniquement des images',
            variant: 'destructive',
          });
        }
      }
    }, [disableDragDrop, disabled, processFiles, toast]);

    // ========================================================================
    // SÉLECTION DE FICHIER
    // ========================================================================

    const handleClick = useCallback(() => {
      if (!disabled && !isMaxImagesReached) {
        inputRefInternal.current?.click();
      }
    }, [disabled, isMaxImagesReached]);

    const handleFileSelect = useCallback((e: ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        processFiles(files);
      }
      e.target.value = '';
    }, [processFiles]);

    // ========================================================================
    // FOCUS / BLUR
    // ========================================================================

    const handleFocus = useCallback(() => {
      setIsFocused(true);
      if (onFocus) onFocus();
    }, [onFocus]);

    const handleBlur = useCallback(() => {
      setIsFocused(false);
      if (onBlur) onBlur();
    }, [onBlur]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined) {
        const val = externalValue ? (Array.isArray(externalValue) ? externalValue : [externalValue]) : null;
        if (JSON.stringify(val) !== JSON.stringify(prevValueRef.current)) {
          prevValueRef.current = val;
        }
      }
    }, [externalValue]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue !== undefined && !isControlled) {
        const val = defaultValue ? (Array.isArray(defaultValue) ? defaultValue : [defaultValue]) : null;
        updateValue(val);
      }
    }, [defaultValue, updateValue, isControlled]);

    // ========================================================================
    // NETTOYAGE
    // ========================================================================

    useEffect(() => {
      return () => {
        if (value) {
          value.forEach(img => {
            if (img.previewUrl) URL.revokeObjectURL(img.previewUrl);
          });
        }
      };
    }, [value]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => inputRefInternal.current?.focus(),
      blur: () => inputRefInternal.current?.blur(),
      getValue: () => value,
      setValue: (images: UploadImage[] | UploadImage | null) => {
        const normalized = images ? (Array.isArray(images) ? images : [images]) : null;
        updateValue(normalized);
      },
      addImages: (files: File[]) => processFiles(files),
      removeImage: (imageId: string) => handleRemoveImage(imageId),
      clearAll: () => handleRemoveAll(),
      validate: () => {
        const validation = validateImages(value);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU DES IMAGES
    // ========================================================================

    const renderImageItem = (image: UploadImage) => {
      const isUploading = image.status === 'uploading';
      const isSuccess = image.status === 'success';
      const isError = image.status === 'error';
      const isSelected = selectedImage === image.id;

      if (viewMode === 'carousel') {
        return (
          <motion.div
            key={image.id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="relative flex-shrink-0 w-full h-full"
          >
            <img
              src={image.previewUrl}
              alt={image.metadata?.alt || image.name}
              className="h-full w-full object-contain"
            />
            {isUploading && showProgress && (
              <div className="absolute bottom-4 left-4 right-4">
                <Progress value={image.progress} className="h-2" />
              </div>
            )}
            {showControls && (
              <div className="absolute top-4 right-4 flex gap-1">
                <button
                  type="button"
                  onClick={() => handleRemoveImage(image.id)}
                  className="rounded-full bg-black/50 p-1.5 text-white hover:bg-black/70 transition-colors"
                  disabled={disabled || isUploading}
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </div>
            )}
          </motion.div>
        );
      }

      return (
        <motion.div
          key={image.id}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.9 }}
          className={cn(
            'group relative rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden',
            viewMode === 'list' ? 'flex items-center gap-4 p-3' : 'aspect-square',
            isError && 'border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/10',
            isSelected && 'ring-2 ring-brand-500'
          )}
          onMouseEnter={() => setSelectedImage(image.id)}
          onMouseLeave={() => setSelectedImage(null)}
        >
          {/* Prévisualisation */}
          {showPreview && (
            <div className={cn(
              'relative overflow-hidden',
              viewMode === 'list' ? 'h-16 w-16 flex-shrink-0 rounded' : 'aspect-square'
            )}>
              <img
                src={image.previewUrl}
                alt={image.metadata?.alt || image.name}
                className="h-full w-full object-cover"
              />
              {isUploading && showProgress && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/50">
                  <div className="text-center">
                    <ArrowPathIcon className="h-8 w-8 animate-spin text-white mx-auto" />
                    <span className="mt-1 block text-xs text-white">{image.progress}%</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Informations */}
          {showInfo && (
            <div className={cn(
              'flex-1 min-w-0',
              viewMode === 'list' ? 'flex-1' : 'absolute bottom-0 left-0 right-0 bg-black/60 p-2 translate-y-full group-hover:translate-y-0 transition-transform'
            )}>
              <p className="text-sm font-medium truncate text-white">
                {image.metadata?.title || image.name}
              </p>
              <p className="text-xs text-gray-300">
                {formatFileSize(image.size)}
                {image.dimensions && ` • ${image.dimensions.width}×${image.dimensions.height}`}
              </p>
            </div>
          )}

          {/* Actions */}
          {showControls && (
            <div className={cn(
              'absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity',
              viewMode === 'list' && 'opacity-100 relative top-0 right-0'
            )}>
              {!disabled && !isUploading && (
                <>
                  {!disableCrop && (
                    <Tooltip content="Recadrer">
                      <button
                        type="button"
                        onClick={() => setCropMode(!cropMode)}
                        className="rounded bg-black/50 p-1.5 text-white hover:bg-black/70 transition-colors"
                      >
                        <CropIcon className="h-4 w-4" />
                      </button>
                    </Tooltip>
                  )}
                  {!disableRotate && (
                    <Tooltip content="Pivoter">
                      <button
                        type="button"
                        onClick={() => {
                          setRotation((prev) => (prev + 90) % 360);
                        }}
                        className="rounded bg-black/50 p-1.5 text-white hover:bg-black/70 transition-colors"
                      >
                        <RotateCwIcon className="h-4 w-4" />
                      </button>
                    </Tooltip>
                  )}
                </>
              )}
              <button
                type="button"
                onClick={() => handleRemoveImage(image.id)}
                className="rounded bg-black/50 p-1.5 text-white hover:bg-black/70 transition-colors"
                disabled={disabled || isUploading}
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>
          )}
        </motion.div>
      );
    };

    // ========================================================================
    // RENDU DE LA ZONE DE DÉPÔT
    // ========================================================================

    const renderDropzone = () => {
      if (isMaxImagesReached && multi) {
        return (
          <div className="rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 p-8 text-center">
            <PhotoIcon className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              Nombre maximum d'images atteint ({maxImages})
            </p>
          </div>
        );
      }

      return (
        <div
          ref={dropAreaRef}
          className={cn(
            'relative rounded-lg border-2 border-dashed transition-all cursor-pointer',
            isDragging && !disabled
              ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
              : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500',
            disabled && 'opacity-50 cursor-not-allowed',
            'flex flex-col items-center justify-center gap-3 p-8'
          )}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onClick={handleClick}
        >
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
            type="file"
            className="hidden"
            multiple={multi}
            accept={accept.join(',')}
            onChange={handleFileSelect}
            onFocus={handleFocus}
            onBlur={handleBlur}
            disabled={disabled}
            id={id || name}
            name={name}
            aria-label={ariaLabel || label}
            aria-describedby={ariaDescribedby}
          />

          <div className={cn(
            'rounded-full p-3',
            isDragging ? 'bg-brand-100 dark:bg-brand-900/30' : 'bg-gray-100 dark:bg-gray-800'
          )}>
            <PhotoIcon className={cn(
              'h-8 w-8',
              isDragging ? 'text-brand-600 dark:text-brand-400' : 'text-gray-500 dark:text-gray-400'
            )} />
          </div>

          <div className="text-center">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {isDragging ? 'Déposez vos images ici' : placeholder}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Formats: {accept.map(f => f.split('/')[1]).join(', ')} • 
              Max: {formatFileSize(maxSize)}
              {multi && ` • Max: ${maxImages} images`}
              {aspectRatio && ` • Ratio: ${aspectRatio}`}
            </p>
          </div>
        </div>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const hasError = !!error || !isValid || (required && imageCount === 0);
    const isSuccess = !hasError && success && imageCount > 0;

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
            {showInfo && multi && (
              <Badge variant="outline" size="sm">
                {imageCount} / {maxImages}
              </Badge>
            )}
          </div>
        )}

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}

        {/* Zone de dépôt */}
        {renderDropzone()}

        {/* Liste des images */}
        {value && value.length > 0 && (
          <div className="mt-3 space-y-2">
            {/* Contrôles d'affichage */}
            {showControls && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {value.length} image{value.length > 1 ? 's' : ''}
                </span>
                <div className="flex items-center gap-1">
                  <Tooltip content="Vue grille">
                    <button
                      type="button"
                      className={cn(
                        'rounded p-1 transition-colors',
                        viewMode === 'grid' ? 'bg-gray-200 dark:bg-gray-700' : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                      )}
                      onClick={() => setViewMode('grid')}
                    >
                      <Squares2X2Icon className="h-4 w-4" />
                    </button>
                  </Tooltip>
                  <Tooltip content="Vue liste">
                    <button
                      type="button"
                      className={cn(
                        'rounded p-1 transition-colors',
                        viewMode === 'list' ? 'bg-gray-200 dark:bg-gray-700' : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                      )}
                      onClick={() => setViewMode('list')}
                    >
                      <ListBulletIcon className="h-4 w-4" />
                    </button>
                  </Tooltip>
                  <Tooltip content="Carrousel">
                    <button
                      type="button"
                      className={cn(
                        'rounded p-1 transition-colors',
                        viewMode === 'carousel' ? 'bg-gray-200 dark:bg-gray-700' : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                      )}
                      onClick={() => setViewMode('carousel')}
                    >
                      <RectangleGroupIcon className="h-4 w-4" />
                    </button>
                  </Tooltip>
                  {value.length > 0 && (
                    <button
                      type="button"
                      onClick={handleRemoveAll}
                      className="rounded p-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                      disabled={disabled}
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Images */}
            <div className={cn(
              viewMode === 'grid' ? 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3' : 'space-y-2',
              viewMode === 'carousel' ? 'relative h-64 overflow-hidden rounded-lg bg-gray-100 dark:bg-gray-800' : ''
            )}>
              <AnimatePresence>
                {value.map(image => renderImageItem(image))}
              </AnimatePresence>
            </div>
          </div>
        )}

        {/* Statut */}
        <div className="mt-1 flex items-center gap-1.5 text-xs">
          {hasError && (
            <span className="text-red-600 dark:text-red-400">
              {error || validationMessage || 'Image invalide'}
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
    );
  }
);

ImageField.displayName = 'ImageField';

// ============================================================================
// EXPORTS
// ============================================================================

export default ImageField;

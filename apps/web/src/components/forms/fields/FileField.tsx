// apps/web/src/components/forms/fields/FileField.tsx
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
  DragEvent,
  ChangeEvent,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CloudArrowUpIcon,
  CloudArrowDownIcon,
  DocumentIcon,
  DocumentTextIcon,
  PhotoIcon,
  VideoCameraIcon,
  MusicalNoteIcon,
  ArchiveBoxIcon,
  CodeBracketIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ArrowPathIcon,
  EyeIcon,
  EyeSlashIcon,
  TrashIcon,
  PencilIcon,
  ArrowsUpDownIcon,
  FolderIcon,
  FolderOpenIcon,
  PaperClipIcon,
  DocumentDuplicateIcon,
  ShareIcon,
  LinkIcon,
  DownloadIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  MinusIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  RectangleGroupIcon,
  Squares2X2Icon,
  ListBulletIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
} from '@heroicons/react/24/solid';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Progress } from '@/components/common/Progress';
import { Tooltip } from '@/components/common/Tooltip';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type FileStatus = 'idle' | 'uploading' | 'success' | 'error' | 'cancelled';
export type FileType = 'image' | 'video' | 'audio' | 'document' | 'archive' | 'code' | 'other';
export type FileUploadVariant = 'default' | 'compact' | 'minimal' | 'dropzone' | 'card';

export interface UploadFile {
  /** Identifiant unique du fichier */
  id: string;
  /** Nom du fichier */
  name: string;
  /** Taille du fichier (bytes) */
  size: number;
  /** Type MIME du fichier */
  type: string;
  /** Extension du fichier */
  extension: string;
  /** Catégorie du fichier */
  fileType: FileType;
  /** Statut du fichier */
  status: FileStatus;
  /** Progression du téléchargement (0-100) */
  progress: number;
  /** URL de prévisualisation */
  previewUrl?: string;
  /** Fichier brut */
  file?: File;
  /** Message d'erreur */
  error?: string;
  /** Métadonnées */
  metadata?: Record<string, any>;
  /** Date d'upload */
  uploadedAt?: Date;
}

export interface FileFieldProps {
  // --- Contrôle ---
  /** Valeur du champ (fichiers) */
  value?: UploadFile[] | null;
  /** Valeur par défaut */
  defaultValue?: UploadFile[] | null;
  /** Callback de changement */
  onChange?: (files: UploadFile[] | null) => void;
  /** Callback de blur */
  onBlur?: () => void;
  /** Callback de focus */
  onFocus?: () => void;
  /** Callback de validation */
  onValidate?: (valid: boolean, files: UploadFile[] | null) => void;

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
  variant?: FileUploadVariant;
  /** Afficher la prévisualisation */
  showPreview?: boolean;
  /** Afficher la progression */
  showProgress?: boolean;
  /** Afficher les contrôles */
  showControls?: boolean;
  /** Afficher les informations du fichier */
  showFileInfo?: boolean;
  /** Afficher le compteur */
  showCounter?: boolean;
  /** Mode grille/liste */
  displayMode?: 'grid' | 'list' | 'compact';

  // --- Comportement ---
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Mode multi-fichiers */
  multi?: boolean;
  /** Nombre maximum de fichiers */
  maxFiles?: number;
  /** Taille maximale par fichier (bytes) */
  maxFileSize?: number;
  /** Taille totale maximale (bytes) */
  maxTotalSize?: number;
  /** Types MIME acceptés */
  accept?: string | string[];
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Désactiver le drag & drop */
  disableDragDrop?: boolean;
  /** Désactiver la prévisualisation */
  disablePreview?: boolean;

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
  customValidate?: (files: UploadFile[] | null) => boolean | string;
  /** Fonction de formatage personnalisée */
  customFormat?: (file: File) => UploadFile;
  /** Ref */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const FILE_SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB'];
const DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const DEFAULT_MAX_FILES = 10;
const ACCEPT_IMAGE = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'];
const ACCEPT_VIDEO = ['video/mp4', 'video/webm', 'video/ogg'];
const ACCEPT_AUDIO = ['audio/mpeg', 'audio/ogg', 'audio/wav'];
const ACCEPT_DOCUMENT = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'];
const ACCEPT_ARCHIVE = ['application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed', 'application/gzip'];
const ACCEPT_CODE = ['text/plain', 'text/html', 'text/css', 'text/javascript', 'application/json', 'application/xml'];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const FileField = forwardRef<HTMLInputElement, FileFieldProps>(
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
      placeholder = 'Déposez vos fichiers ici ou cliquez pour parcourir',
      description,
      error,
      success,
      info,
      variant = 'default',
      showPreview = true,
      showProgress = true,
      showControls = true,
      showFileInfo = true,
      showCounter = true,
      displayMode = 'grid',

      // Comportement
      disabled = false,
      required = false,
      multi = true,
      maxFiles = DEFAULT_MAX_FILES,
      maxFileSize = DEFAULT_MAX_FILE_SIZE,
      maxTotalSize,
      accept,
      disableRealtimeValidation = false,
      disableDragDrop = false,
      disablePreview = false,

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
    const prevValueRef = useRef<UploadFile[] | null>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState<UploadFile[] | null>(
      defaultValue || null
    );
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');
    const [isDragging, setIsDragging] = useState(false);
    const [uploadingFiles, setUploadingFiles] = useState<Set<string>>(new Set());
    const [viewMode, setViewMode] = useState<'grid' | 'list' | 'compact'>(displayMode);
    const [selectedFile, setSelectedFile] = useState<string | null>(null);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const fileCount = value?.length || 0;
    const totalSize = value?.reduce((acc, f) => acc + f.size, 0) || 0;
    const isMaxFilesReached = multi && fileCount >= maxFiles;

    // ========================================================================
    // UTILITAIRES
    // ========================================================================

    const formatFileSize = useCallback((bytes: number): string => {
      if (bytes === 0) return '0 B';
      const i = Math.floor(Math.log(bytes) / Math.log(1024));
      const size = bytes / Math.pow(1024, i);
      return `${size.toFixed(1)} ${FILE_SIZE_UNITS[i]}`;
    }, []);

    const getFileType = useCallback((mimeType: string): FileType => {
      if (mimeType.startsWith('image/')) return 'image';
      if (mimeType.startsWith('video/')) return 'video';
      if (mimeType.startsWith('audio/')) return 'audio';
      if (mimeType.includes('pdf') || mimeType.includes('word') || mimeType.includes('excel')) return 'document';
      if (mimeType.includes('zip') || mimeType.includes('rar') || mimeType.includes('7z')) return 'archive';
      if (mimeType.includes('text') || mimeType.includes('javascript') || mimeType.includes('json')) return 'code';
      return 'other';
    }, []);

    const getFileExtension = useCallback((filename: string): string => {
      return filename.split('.').pop()?.toLowerCase() || '';
    }, []);

    const generateFileId = useCallback(() => {
      return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    }, []);

    const createUploadFile = useCallback((file: File): UploadFile => {
      const extension = getFileExtension(file.name);
      const fileType = getFileType(file.type);
      
      return {
        id: generateFileId(),
        name: file.name,
        size: file.size,
        type: file.type,
        extension,
        fileType,
        status: 'idle',
        progress: 0,
        file,
        uploadedAt: new Date(),
      };
    }, [getFileExtension, getFileType, generateFileId]);

    const getFileIcon = useCallback((fileType: FileType) => {
      switch (fileType) {
        case 'image':
          return <PhotoIcon className="h-5 w-5" />;
        case 'video':
          return <VideoCameraIcon className="h-5 w-5" />;
        case 'audio':
          return <MusicalNoteIcon className="h-5 w-5" />;
        case 'document':
          return <DocumentTextIcon className="h-5 w-5" />;
        case 'archive':
          return <ArchiveBoxIcon className="h-5 w-5" />;
        case 'code':
          return <CodeBracketIcon className="h-5 w-5" />;
        default:
          return <DocumentIcon className="h-5 w-5" />;
      }
    }, []);

    const getFileColor = useCallback((fileType: FileType) => {
      switch (fileType) {
        case 'image':
          return 'bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400';
        case 'video':
          return 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400';
        case 'audio':
          return 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400';
        case 'document':
          return 'bg-orange-50 dark:bg-orange-900/20 text-orange-600 dark:text-orange-400';
        case 'archive':
          return 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-600 dark:text-yellow-400';
        case 'code':
          return 'bg-gray-50 dark:bg-gray-800/50 text-gray-600 dark:text-gray-400';
        default:
          return 'bg-gray-50 dark:bg-gray-800/50 text-gray-600 dark:text-gray-400';
      }
    }, []);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateFiles = useCallback((files: UploadFile[] | null): { valid: boolean; message: string } => {
      if (customValidate) {
        const result = customValidate(files);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (!files || files.length === 0) {
        if (required) {
          return { valid: false, message: 'Veuillez sélectionner au moins un fichier' };
        }
        return { valid: true, message: '' };
      }

      // Vérifier le nombre maximum de fichiers
      if (multi && files.length > maxFiles) {
        return { valid: false, message: `Maximum ${maxFiles} fichier${maxFiles > 1 ? 's' : ''} autorisé${maxFiles > 1 ? 's' : ''}` };
      }

      // Vérifier la taille de chaque fichier
      for (const file of files) {
        if (file.size > maxFileSize) {
          return { valid: false, message: `Le fichier "${file.name}" dépasse la taille maximale (${formatFileSize(maxFileSize)})` };
        }
      }

      // Vérifier la taille totale
      if (maxTotalSize) {
        const total = files.reduce((sum, f) => sum + f.size, 0);
        if (total > maxTotalSize) {
          return { valid: false, message: `La taille totale des fichiers dépasse la limite (${formatFileSize(maxTotalSize)})` };
        }
      }

      // Vérifier les types MIME
      if (accept) {
        const acceptedTypes = Array.isArray(accept) ? accept : [accept];
        for (const file of files) {
          const isAccepted = acceptedTypes.some(type => {
            if (type.includes('*')) {
              const [prefix] = type.split('/');
              return file.type.startsWith(prefix);
            }
            return file.type === type;
          });
          if (!isAccepted) {
            return { valid: false, message: `Le fichier "${file.name}" n'est pas d'un type accepté` };
          }
        }
      }

      return { valid: true, message: '' };
    }, [customValidate, required, multi, maxFiles, maxFileSize, maxTotalSize, accept, formatFileSize]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((files: UploadFile[] | null) => {
      const validation = validateFiles(files);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, files);
      }

      if (isControlled) {
        if (onChange) onChange(files);
      } else {
        setInternalValue(files);
        if (onChange) onChange(files);
      }

      if (debug) {
        console.log('FileField update:', { files, count: files?.length || 0, isValid: validation.valid });
      }
    }, [validateFiles, isControlled, onChange, onValidate, disableRealtimeValidation, debug]);

    // ========================================================================
    // GESTION DES FICHIERS
    // ========================================================================

    const processFiles = useCallback((fileList: FileList | File[]) => {
      const files = Array.from(fileList);
      
      // Vérifier le nombre maximum
      if (multi && fileCount + files.length > maxFiles) {
        toast({
          title: 'Limite de fichiers atteinte',
          description: `Maximum ${maxFiles} fichier${maxFiles > 1 ? 's' : ''} autorisé${maxFiles > 1 ? 's' : ''}`,
          variant: 'destructive',
        });
        return;
      }

      const newFiles: UploadFile[] = [];
      const errors: string[] = [];

      for (const file of files) {
        // Vérifier la taille
        if (file.size > maxFileSize) {
          errors.push(`"${file.name}" dépasse la taille maximale (${formatFileSize(maxFileSize)})`);
          continue;
        }

        // Vérifier le type
        if (accept) {
          const acceptedTypes = Array.isArray(accept) ? accept : [accept];
          const isAccepted = acceptedTypes.some(type => {
            if (type.includes('*')) {
              const [prefix] = type.split('/');
              return file.type.startsWith(prefix);
            }
            return file.type === type;
          });
          if (!isAccepted) {
            errors.push(`"${file.name}" n'est pas d'un type accepté`);
            continue;
          }
        }

        const uploadFile = customFormat ? customFormat(file) : createUploadFile(file);
        newFiles.push(uploadFile);
      }

      if (errors.length > 0) {
        toast({
          title: 'Erreurs de validation',
          description: errors.join('\n'),
          variant: 'destructive',
          duration: 5000,
        });
      }

      if (newFiles.length > 0) {
        const currentFiles = value || [];
        const updatedFiles = multi ? [...currentFiles, ...newFiles] : newFiles;
        updateValue(updatedFiles);
        
        // Simuler l'upload
        if (showProgress) {
          newFiles.forEach((file) => {
            simulateUpload(file.id);
          });
        }
      }
    }, [
      multi,
      maxFiles,
      fileCount,
      maxFileSize,
      accept,
      formatFileSize,
      customFormat,
      createUploadFile,
      value,
      updateValue,
      showProgress,
      toast,
    ]);

    // ========================================================================
    // SIMULATION D'UPLOAD
    // ========================================================================

    const simulateUpload = useCallback((fileId: string) => {
      setUploadingFiles(prev => new Set([...prev, fileId]));
      
      let progress = 0;
      const interval = setInterval(() => {
        progress += Math.random() * 20;
        if (progress >= 100) {
          progress = 100;
          clearInterval(interval);
          // Mettre à jour le statut du fichier
          updateFileStatus(fileId, 'success', 100);
          setUploadingFiles(prev => {
            const next = new Set(prev);
            next.delete(fileId);
            return next;
          });
          toast({
            title: 'Fichier téléchargé',
            description: 'Le fichier a été téléchargé avec succès',
            duration: 2000,
          });
        } else {
          updateFileProgress(fileId, Math.round(progress));
        }
      }, 200);
    }, []);

    const updateFileProgress = useCallback((fileId: string, progress: number) => {
      if (!value) return;
      const updated = value.map(f => 
        f.id === fileId ? { ...f, progress, status: 'uploading' as FileStatus } : f
      );
      updateValue(updated);
    }, [value, updateValue]);

    const updateFileStatus = useCallback((fileId: string, status: FileStatus, progress: number) => {
      if (!value) return;
      const updated = value.map(f => 
        f.id === fileId ? { ...f, status, progress } : f
      );
      updateValue(updated);
    }, [value, updateValue]);

    // ========================================================================
    // SUPPRESSION DE FICHIER
    // ========================================================================

    const handleRemoveFile = useCallback((fileId: string) => {
      if (!value) return;
      const updated = value.filter(f => f.id !== fileId);
      updateValue(updated.length > 0 ? updated : null);
      toast({
        title: 'Fichier supprimé',
        description: 'Le fichier a été retiré de la liste',
        duration: 2000,
      });
    }, [value, updateValue, toast]);

    const handleRemoveAll = useCallback(() => {
      updateValue(null);
      toast({
        title: 'Fichiers supprimés',
        description: 'Tous les fichiers ont été retirés',
        duration: 2000,
      });
    }, [updateValue, toast]);

    // ========================================================================
    // GESTION DU DRAG & DROP
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
        processFiles(files);
      }
    }, [disableDragDrop, disabled, processFiles]);

    // ========================================================================
    // GESTION DU CLIC
    // ========================================================================

    const handleClick = useCallback(() => {
      if (!disabled && !isMaxFilesReached) {
        inputRefInternal.current?.click();
      }
    }, [disabled, isMaxFilesReached]);

    const handleFileSelect = useCallback((e: ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        processFiles(files);
      }
      // Réinitialiser pour permettre la sélection du même fichier
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
        const val = externalValue;
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
        updateValue(defaultValue);
      }
    }, [defaultValue, updateValue, isControlled]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => inputRefInternal.current?.focus(),
      blur: () => inputRefInternal.current?.blur(),
      getValue: () => value,
      setValue: (files: UploadFile[] | null) => updateValue(files),
      addFiles: (files: File[]) => processFiles(files),
      removeFile: (fileId: string) => handleRemoveFile(fileId),
      clearAll: () => handleRemoveAll(),
      validate: () => {
        const validation = validateFiles(value);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU DES FICHIERS
    // ========================================================================

    const renderFileItem = (file: UploadFile) => {
      const isUploading = file.status === 'uploading';
      const isSuccess = file.status === 'success';
      const isError = file.status === 'error';
      const fileColor = getFileColor(file.fileType);
      const fileIcon = getFileIcon(file.fileType);

      if (viewMode === 'compact') {
        return (
          <div
            key={file.id}
            className={cn(
              'flex items-center gap-3 rounded-lg border border-gray-200 dark:border-gray-700 p-2',
              isError && 'border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/10'
            )}
          >
            <div className={cn('flex h-8 w-8 items-center justify-center rounded', fileColor)}>
              {fileIcon}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{file.name}</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">{formatFileSize(file.size)}</p>
            </div>
            {isUploading && showProgress && (
              <Progress value={file.progress} className="w-16 h-1" />
            )}
            {isSuccess && (
              <CheckCircleIcon className="h-4 w-4 text-green-500" />
            )}
            {isError && (
              <ExclamationTriangleIcon className="h-4 w-4 text-red-500" />
            )}
            <button
              type="button"
              onClick={() => handleRemoveFile(file.id)}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              disabled={disabled || isUploading}
            >
              <XMarkIcon className="h-4 w-4" />
            </button>
          </div>
        );
      }

      return (
        <motion.div
          key={file.id}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.9 }}
          className={cn(
            'group relative rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden',
            viewMode === 'list' ? 'flex items-center gap-4 p-3' : 'p-3',
            isError && 'border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/10'
          )}
        >
          {/* Prévisualisation */}
          {showPreview && file.fileType === 'image' && file.file && (
            <div className={cn(
              'relative overflow-hidden',
              viewMode === 'list' ? 'h-12 w-12 flex-shrink-0 rounded' : 'h-32 w-full rounded'
            )}>
              <img
                src={URL.createObjectURL(file.file)}
                alt={file.name}
                className="h-full w-full object-cover"
                onLoad={(e) => {
                  // Libérer l'URL après le chargement
                  URL.revokeObjectURL((e.target as HTMLImageElement).src);
                }}
              />
            </div>
          )}

          {/* Icône */}
          {(!showPreview || file.fileType !== 'image') && (
            <div className={cn(
              'flex items-center justify-center',
              viewMode === 'list' ? 'h-12 w-12 flex-shrink-0 rounded' : 'h-16 w-16 mx-auto rounded',
              fileColor
            )}>
              {fileIcon}
            </div>
          )}

          {/* Informations */}
          <div className={cn(
            'flex-1 min-w-0',
            viewMode === 'list' ? 'flex-1' : 'text-center'
          )}>
            <p className={cn(
              'font-medium truncate',
              viewMode === 'list' ? 'text-sm' : 'text-sm mt-2'
            )}>
              {file.name}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {formatFileSize(file.size)} • {file.extension.toUpperCase()}
            </p>
            {isUploading && showProgress && (
              <div className="mt-1">
                <Progress value={file.progress} className="h-1" />
                <p className="text-xs text-gray-400 mt-0.5">{file.progress}%</p>
              </div>
            )}
            {isError && file.error && (
              <p className="text-xs text-red-500 mt-1">{file.error}</p>
            )}
          </div>

          {/* Actions */}
          {showControls && (
            <div className={cn(
              'flex items-center gap-1',
              viewMode === 'list' ? 'flex-shrink-0' : 'absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity'
            )}>
              {isSuccess && (
                <Tooltip content="Téléchargé avec succès">
                  <CheckCircleIcon className="h-4 w-4 text-green-500" />
                </Tooltip>
              )}
              {isError && (
                <Tooltip content="Erreur de téléchargement">
                  <ExclamationTriangleIcon className="h-4 w-4 text-red-500" />
                </Tooltip>
              )}
              <button
                type="button"
                onClick={() => handleRemoveFile(file.id)}
                className="rounded p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
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
      if (isMaxFilesReached && multi) {
        return (
          <div className="rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 p-8 text-center">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Nombre maximum de fichiers atteint ({maxFiles})
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
            variant === 'dropzone' && 'p-12',
            variant === 'compact' && 'p-4',
            variant === 'minimal' && 'p-3 border-0 bg-gray-50 dark:bg-gray-800/50',
            variant === 'card' && 'p-6 bg-white dark:bg-gray-900 shadow-sm',
            'flex flex-col items-center justify-center gap-3'
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
            accept={Array.isArray(accept) ? accept.join(',') : accept}
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
            <CloudArrowUpIcon className={cn(
              'h-6 w-6',
              isDragging ? 'text-brand-600 dark:text-brand-400' : 'text-gray-500 dark:text-gray-400'
            )} />
          </div>

          <div className="text-center">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {isDragging ? 'Déposez vos fichiers ici' : placeholder}
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              {accept && (
                <span>Types acceptés: {Array.isArray(accept) ? accept.join(', ') : accept} • </span>
              )}
              Taille max: {formatFileSize(maxFileSize)}
              {multi && ` • Max: ${maxFiles} fichiers`}
            </p>
          </div>
        </div>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const hasError = !!error || !isValid || (required && fileCount === 0);
    const isSuccess = !hasError && success && fileCount > 0;

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
            {showCounter && multi && (
              <Badge variant="outline" size="sm">
                {fileCount} / {maxFiles}
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

        {/* Liste des fichiers */}
        {value && value.length > 0 && (
          <div className="mt-3 space-y-2">
            {/* Contrôles d'affichage */}
            {showControls && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {value.length} fichier{value.length > 1 ? 's' : ''} • {formatFileSize(totalSize)}
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
                  <Tooltip content="Vue compacte">
                    <button
                      type="button"
                      className={cn(
                        'rounded p-1 transition-colors',
                        viewMode === 'compact' ? 'bg-gray-200 dark:bg-gray-700' : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                      )}
                      onClick={() => setViewMode('compact')}
                    >
                      <RectangleGroupIcon className="h-4 w-4" />
                    </button>
                  </Tooltip>
                  <button
                    type="button"
                    onClick={handleRemoveAll}
                    className="rounded p-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                    disabled={disabled}
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}

            {/* Fichiers */}
            <div className={cn(
              viewMode === 'grid' ? 'grid grid-cols-1 sm:grid-cols-2 gap-3' : 'space-y-2'
            )}>
              <AnimatePresence>
                {value.map(file => renderFileItem(file))}
              </AnimatePresence>
            </div>
          </div>
        )}

        {/* Statut */}
        <div className="mt-1 flex items-center gap-1.5 text-xs">
          {hasError && (
            <span className="text-red-600 dark:text-red-400">
              {error || validationMessage || 'Fichier invalide'}
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

FileField.displayName = 'FileField';

// ============================================================================
// EXPORTS
// ============================================================================

export default FileField;

/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import { cn } from '@/utils/helpers';
import { Loader2, AlertCircle, ImageOff } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface ImageProps
  extends React.ImgHTMLAttributes<HTMLImageElement> {
  src: string;
  alt: string;
  width?: number;
  height?: number;
  fill?: boolean;
  sizes?: string;
  quality?: number;
  priority?: boolean;
  loading?: 'lazy' | 'eager';
  placeholder?: 'blur' | 'empty' | 'color';
  blurDataURL?: string;
  onLoadingComplete?: (event: React.SyntheticEvent<HTMLImageElement>) => void;
  onError?: (event: React.SyntheticEvent<HTMLImageElement>) => void;
  fallback?: React.ReactNode;
  fallbackSrc?: string;
  objectFit?: 'cover' | 'contain' | 'fill' | 'none' | 'scale-down';
  objectPosition?: string;
  className?: string;
  containerClassName?: string;
  imageClassName?: string;
  loader?: (src: string, width: number, quality?: number) => string;
  unoptimized?: boolean;
  lazyBoundary?: string;
  lazyRoot?: React.RefObject<HTMLElement> | null;
}

// ============================================
// COMPOSANT
// ============================================

export function Image({
  src,
  alt,
  width,
  height,
  fill = false,
  sizes = '100vw',
  quality = 75,
  priority = false,
  loading = 'lazy',
  placeholder = 'empty',
  blurDataURL,
  onLoadingComplete,
  onError,
  fallback,
  fallbackSrc,
  objectFit = 'cover',
  objectPosition = 'center',
  className,
  containerClassName,
  imageClassName,
  loader,
  unoptimized = false,
  lazyBoundary = '200px',
  lazyRoot = null,
  ...props
}: ImageProps) {
  // ============================================
  // RÉFÉRENCES
  // ============================================
  const imgRef = React.useRef<HTMLImageElement>(null);
  const [isLoaded, setIsLoaded] = React.useState(false);
  const [hasError, setHasError] = React.useState(false);
  const [isLoading, setIsLoading] = React.useState(true);

  // ============================================
  // EFFETS
  // ============================================

  // Réinitialiser les états lorsque la source change
  React.useEffect(() => {
    setIsLoaded(false);
    setHasError(false);
    setIsLoading(true);
  }, [src]);

  // ============================================
  // FONCTIONS
  // ============================================

  const handleLoad = (event: React.SyntheticEvent<HTMLImageElement>) => {
    setIsLoaded(true);
    setIsLoading(false);
    onLoadingComplete?.(event);
  };

  const handleError = (event: React.SyntheticEvent<HTMLImageElement>) => {
    setHasError(true);
    setIsLoading(false);
    onError?.(event);

    // Si on a une source de fallback, on peut la charger
    if (fallbackSrc) {
      const img = event.currentTarget;
      img.src = fallbackSrc;
      // Empêcher la boucle infinie
      img.onerror = null;
    }
  };

  // ============================================
  // GÉNÉRATION DE L'URL
  // ============================================

  const getImageSrc = React.useCallback(() => {
    if (!src) return '';
    if (unoptimized || !loader) return src;

    // Si width est défini, utiliser le loader
    if (width) {
      return loader(src, width, quality);
    }

    // Si fill est true, utiliser une largeur par défaut
    if (fill) {
      return loader(src, 1200, quality);
    }

    return src;
  }, [src, loader, width, quality, fill, unoptimized]);

  // ============================================
  // STYLES
  // ============================================

  const containerStyles = cn(
    'relative overflow-hidden',
    fill ? 'w-full h-full' : '',
    containerClassName
  );

  const imageStyles = cn(
    'transition-opacity duration-300',
    !isLoaded && isLoading && 'opacity-0',
    isLoaded && 'opacity-100',
    hasError && 'opacity-0',
    fill ? 'absolute inset-0' : '',
    imageClassName || className
  );

  const objectFitStyles = {
    cover: 'object-cover',
    contain: 'object-contain',
    fill: 'object-fill',
    none: 'object-none',
    'scale-down': 'object-scale-down',
  };

  const objectPositionStyles = {
    center: 'object-center',
    top: 'object-top',
    bottom: 'object-bottom',
    left: 'object-left',
    right: 'object-right',
    'top-left': 'object-top-left',
    'top-right': 'object-top-right',
    'bottom-left': 'object-bottom-left',
    'bottom-right': 'object-bottom-right',
  };

  // ============================================
  // PLACEHOLDER
  // ============================================

  const renderPlaceholder = () => {
    if (hasError) {
      return fallback || (
        <div className="flex h-full w-full items-center justify-center bg-gray-100 dark:bg-gray-800">
          <ImageOff className="h-8 w-8 text-gray-400" />
        </div>
      );
    }

    if (isLoading && placeholder !== 'empty') {
      if (placeholder === 'blur' && blurDataURL) {
        return (
          <img
            src={blurDataURL}
            alt=""
            className={cn(
              'absolute inset-0 h-full w-full object-cover',
              imageStyles
            )}
            aria-hidden="true"
          />
        );
      }

      if (placeholder === 'color') {
        return (
          <div className="absolute inset-0 animate-pulse bg-gray-200 dark:bg-gray-700" />
        );
      }

      return (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 dark:bg-gray-800">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      );
    }

    return null;
  };

  // ============================================
  // RENDU
  // ============================================

  // Si la source est manquante, afficher le fallback
  if (!src) {
    return (
      <div
        className={cn(
          containerStyles,
          'flex items-center justify-center bg-gray-100 dark:bg-gray-800',
          className
        )}
        style={props.style}
      >
        {fallback || (
          <div className="flex flex-col items-center gap-2 text-gray-400">
            <ImageOff className="h-12 w-12" />
            <span className="text-sm">Aucune image</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      className={containerStyles}
      style={{
        width: !fill && width ? width : undefined,
        height: !fill && height ? height : undefined,
        ...props.style,
      }}
    >
      {renderPlaceholder()}

      <img
        ref={imgRef}
        src={getImageSrc()}
        alt={alt}
        width={!fill ? width : undefined}
        height={!fill ? height : undefined}
        sizes={sizes}
        loading={priority ? 'eager' : loading}
        decoding={priority ? 'sync' : 'async'}
        className={cn(
          imageStyles,
          objectFitStyles[objectFit as keyof typeof objectFitStyles] || 'object-cover',
          objectPositionStyles[objectPosition as keyof typeof objectPositionStyles] || 'object-center',
          fill && 'absolute inset-0 h-full w-full'
        )}
        onLoad={handleLoad}
        onError={handleError}
        style={{
          objectPosition: objectPosition,
        }}
        {...props}
      />

      {/* Skeleton de chargement */}
      {isLoading && !hasError && placeholder === 'empty' && (
        <div className="absolute inset-0 animate-pulse bg-gray-200 dark:bg-gray-700" />
      )}
    </div>
  );
}

// ============================================
// EXPORTATIONS
// ============================================

export default Image;

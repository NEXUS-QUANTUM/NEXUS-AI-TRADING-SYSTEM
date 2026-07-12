// apps/web/src/components/common/ScrollArea.tsx
'use client';

import React, {
  ReactNode,
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  forwardRef,
  Ref,
  createContext,
  useContext,
  useId,
  Children,
  isValidElement,
  cloneElement,
  UIEvent,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence, MotionConfig } from 'framer-motion';
import {
  ChevronUpIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
  PlusIcon,
  MinusIcon,
  ArrowsUpDownIcon,
  ArrowsLeftRightIcon,
  ArrowsPointingOutIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';

// ============================================================================
// TYPES
// ============================================================================

export type ScrollDirection = 'vertical' | 'horizontal' | 'both';
export type ScrollBarVisibility = 'auto' | 'always' | 'hover' | 'hidden';
export type ScrollBarPosition = 'inside' | 'outside' | 'overlay';
export type ScrollBarSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type ScrollVariant = 'default' | 'minimal' | 'rounded' | 'gradient' | 'custom';
export type ScrollSnapType = 'none' | 'proximity' | 'mandatory';

export interface ScrollAreaProps {
  // --- Contenu ---
  /** Contenu à faire défiler */
  children: ReactNode;
  /** Contenu alternatif (fallback) */
  fallback?: ReactNode;

  // --- Apparence ---
  /** Variante d'affichage */
  variant?: ScrollVariant;
  /** Taille des barres de défilement */
  size?: ScrollBarSize;
  /** Position des barres de défilement */
  position?: ScrollBarPosition;
  /** Visibilité des barres de défilement */
  visibility?: ScrollBarVisibility;
  /** Direction du défilement */
  direction?: ScrollDirection;
  /** Couleur personnalisée des barres */
  barColor?: string;
  /** Couleur de fond des barres */
  trackColor?: string;
  /** Épaisseur des barres */
  barThickness?: number;
  /** Rayon de bordure des barres */
  barRadius?: string | number;
  /** Classes additionnelles */
  className?: string;
  /** Classes pour le conteneur */
  containerClassName?: string;
  /** Classes pour la barre de défilement */
  barClassName?: string;
  /** Classes pour la piste */
  trackClassName?: string;

  // --- Comportement ---
  /** Hauteur maximale */
  maxHeight?: string | number;
  /** Hauteur minimale */
  minHeight?: string | number;
  /** Largeur maximale */
  maxWidth?: string | number;
  /** Largeur minimale */
  minWidth?: string | number;
  /** Désactiver le défilement */
  disabled?: boolean;
  /** Désactiver le défilement horizontal */
  disableHorizontal?: boolean;
  /** Désactiver le défilement vertical */
  disableVertical?: boolean;
  /** Désactiver le zoom */
  disableZoom?: boolean;
  /** Facteur de zoom */
  zoomFactor?: number;
  /** Zoom minimal */
  minZoom?: number;
  /** Zoom maximal */
  maxZoom?: number;
  /** Zoom par défaut */
  defaultZoom?: number;
  /** Snap type */
  snapType?: ScrollSnapType;
  /** Snap align */
  snapAlign?: 'start' | 'center' | 'end';
  /** Snap stop */
  snapStop?: 'normal' | 'always';

  // --- Contrôle du défilement ---
  /** Position de défilement contrôlée (pour vertical) */
  scrollTop?: number;
  /** Position de défilement contrôlée (pour horizontal) */
  scrollLeft?: number;
  /** Callback lors du défilement */
  onScroll?: (event: UIEvent<HTMLDivElement>) => void;
  /** Callback lors du défilement (avec position) */
  onScrollPosition?: (top: number, left: number) => void;
  /** Callback lors du début du défilement */
  onScrollStart?: () => void;
  /** Callback lors de la fin du défilement */
  onScrollEnd?: () => void;
  /** Callback lors du zoom */
  onZoom?: (zoom: number) => void;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ARIA describedby */
  ariaDescribedby?: string;
  /** ID */
  id?: string;
  /** Rôle ARIA */
  role?: string;

  // --- Avancé ---
  /** Rendre le contenu en dehors de la zone de défilement */
  overflow?: 'visible' | 'hidden' | 'scroll' | 'auto';
  /** Padding interne */
  padding?: string | number;
  /** Smooth scrolling */
  smoothScroll?: boolean;
  /** Délai d'animation (ms) */
  scrollDuration?: number;
  /** Délai avant la disparition des barres (ms) */
  hideDelay?: number;
  /** Désactiver le style par défaut */
  disableDefaultStyles?: boolean;
  /** Observer le contenu pour les changements de taille */
  observeContent?: boolean;
  /** Auto-scroll en bas */
  autoScroll?: boolean;
  /** Auto-scroll au chargement */
  autoScrollOnMount?: boolean;
  /** Callback lors du chargement */
  onLoad?: () => void;

  // --- Ref ---
  /** Ref du conteneur de défilement */
  viewportRef?: React.RefObject<HTMLDivElement>;
}

// ============================================================================
// CONTEXT
// ============================================================================

interface ScrollAreaContextType {
  scrollTop: number;
  scrollLeft: number;
  maxScrollTop: number;
  maxScrollLeft: number;
  isScrolling: boolean;
  zoom: number;
  direction: ScrollDirection;
  size: ScrollBarSize;
  variant: ScrollVariant;
  visibility: ScrollBarVisibility;
  position: ScrollBarPosition;
  disabled: boolean;
  scrollTo: (top: number, left: number, smooth?: boolean) => void;
  scrollToTop: (smooth?: boolean) => void;
  scrollToBottom: (smooth?: boolean) => void;
  scrollToLeft: (smooth?: boolean) => void;
  scrollToRight: (smooth?: boolean) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  resetZoom: () => void;
  registerScrollArea: (id: string) => void;
  unregisterScrollArea: (id: string) => void;
}

const ScrollAreaContext = createContext<ScrollAreaContextType | null>(null);

export const useScrollAreaContext = () => {
  const context = useContext(ScrollAreaContext);
  if (!context) {
    throw new Error('useScrollAreaContext must be used within a ScrollArea');
  }
  return context;
};

// ============================================================================
// COMPOSANTS INTERNES
// ============================================================================

// --- Barre de défilement ---
interface ScrollBarProps {
  orientation: 'vertical' | 'horizontal';
  value: number;
  maxValue: number;
  size: ScrollBarSize;
  variant: ScrollVariant;
  visibility: ScrollBarVisibility;
  position: ScrollBarPosition;
  barColor?: string;
  trackColor?: string;
  barThickness?: number;
  barRadius?: string | number;
  isScrolling: boolean;
  disabled: boolean;
  className?: string;
  trackClassName?: string;
  onScroll: (value: number) => void;
}

const ScrollBar: React.FC<ScrollBarProps> = ({
  orientation,
  value,
  maxValue,
  size,
  variant,
  visibility,
  position,
  barColor,
  trackColor,
  barThickness,
  barRadius,
  isScrolling,
  disabled,
  className,
  trackClassName,
  onScroll,
}) => {
  const isVertical = orientation === 'vertical';
  const [isHovered, setIsHovered] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef<{ value: number; position: number } | null>(null);
  const barRef = useRef<HTMLDivElement>(null);

  // Taille des barres
  const sizeMap = {
    xs: { bar: 'w-1.5 h-1.5', track: 'w-1.5 h-1.5' },
    sm: { bar: 'w-2 h-2', track: 'w-2 h-2' },
    md: { bar: 'w-2.5 h-2.5', track: 'w-2.5 h-2.5' },
    lg: { bar: 'w-3 h-3', track: 'w-3 h-3' },
    xl: { bar: 'w-4 h-4', track: 'w-4 h-4' },
  };

  // Visibilité
  const getVisibility = useCallback(() => {
    if (disabled) return 'hidden';
    if (visibility === 'always' || isScrolling) return 'visible';
    if (visibility === 'hover' && isHovered) return 'visible';
    if (visibility === 'auto' && (isScrolling || isHovered)) return 'visible';
    if (maxValue <= 0) return 'hidden';
    return 'hidden';
  }, [visibility, isScrolling, isHovered, disabled, maxValue]);

  const isVisible = getVisibility();

  // Style des barres
  const barStyles: React.CSSProperties = {
    ...(barThickness && {
      [isVertical ? 'width' : 'height']: barThickness,
    }),
    ...(barRadius && { borderRadius: barRadius }),
    ...(barColor && { backgroundColor: barColor }),
  };

  const trackStyles: React.CSSProperties = {
    ...(trackColor && { backgroundColor: trackColor }),
  };

  // Pourcentage de la barre
  const percentage = maxValue > 0 ? (value / maxValue) * 100 : 0;
  const barSize = isVertical ? `height: ${percentage}%` : `width: ${percentage}%`;

  // Position de la barre
  const barPosition = isVertical ? `top: ${percentage}%` : `left: ${percentage}%`;

  // Gestion du drag
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (disabled) return;
    setIsDragging(true);
    dragStartRef.current = {
      value: value,
      position: isVertical ? e.clientY : e.clientX,
    };
  }, [disabled, value, isVertical]);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!dragStartRef.current) return;
      const delta = (isVertical ? e.clientY : e.clientX) - dragStartRef.current.position;
      const containerSize = isVertical ? window.innerHeight : window.innerWidth;
      const deltaRatio = delta / containerSize;
      const newValue = Math.max(0, Math.min(maxValue, dragStartRef.current.value + deltaRatio * maxValue));
      onScroll(newValue);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      dragStartRef.current = null;
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, isVertical, maxValue, onScroll]);

  if (isVisible === 'hidden') return null;

  return (
    <div
      className={cn(
        'absolute flex touch-none select-none transition-opacity duration-200',
        isVertical
          ? 'right-0 top-0 h-full flex-col items-center'
          : 'bottom-0 left-0 w-full flex-row items-center',
        position === 'inside' && isVertical && 'right-0',
        position === 'inside' && !isVertical && 'bottom-0',
        position === 'outside' && isVertical && '-right-1',
        position === 'outside' && !isVertical && '-bottom-1',
        position === 'overlay' && 'pointer-events-none',
        sizeMap[size]?.track,
        trackClassName
      )}
      style={trackStyles}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div
        ref={barRef}
        className={cn(
          'relative transition-all duration-150',
          isVertical ? 'w-full' : 'h-full',
          sizeMap[size]?.bar,
          variant === 'default' && 'bg-gray-400 hover:bg-gray-500 dark:bg-gray-600 dark:hover:bg-gray-500',
          variant === 'minimal' && 'bg-gray-300 hover:bg-gray-400 dark:bg-gray-700 dark:hover:bg-gray-600',
          variant === 'rounded' && 'bg-gray-400 hover:bg-gray-500 dark:bg-gray-600 dark:hover:bg-gray-500 rounded-full',
          variant === 'gradient' && 'bg-gradient-to-b from-gray-400 to-gray-500 dark:from-gray-600 dark:to-gray-500',
          variant === 'custom' && '',
          (isScrolling || isHovered || isDragging) && 'opacity-100',
          !isScrolling && !isHovered && !isDragging && 'opacity-40',
          position === 'overlay' && 'pointer-events-auto',
          className
        )}
        style={barStyles}
        onMouseDown={handleMouseDown}
        role="scrollbar"
        aria-orientation={orientation}
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={maxValue}
        aria-controls="scroll-area"
        tabIndex={0}
      />
    </div>
  );
};

// --- Contrôles de navigation ---
interface ScrollControlsProps {
  className?: string;
}

const ScrollControls: React.FC<ScrollControlsProps> = ({ className }) => {
  const context = useScrollAreaContext();
  const {
    scrollTop,
    scrollLeft,
    maxScrollTop,
    maxScrollLeft,
    isScrolling,
    scrollToTop,
    scrollToBottom,
    scrollToLeft,
    scrollToRight,
    zoomIn,
    zoomOut,
    resetZoom,
    zoom,
  } = context;

  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    setIsVisible(true);
    const timer = setTimeout(() => setIsVisible(false), 3000);
    return () => clearTimeout(timer);
  }, [scrollTop, scrollLeft]);

  if (!isVisible) return null;

  return (
    <div
      className={cn(
        'absolute bottom-4 right-4 flex items-center gap-1 rounded-lg bg-white/90 dark:bg-gray-900/90 p-1 shadow-lg backdrop-blur-sm',
        className
      )}
    >
      <Tooltip content="Haut">
        <Button
          variant="ghost"
          size="xs"
          className="h-7 w-7 p-0"
          onClick={() => scrollToTop()}
          disabled={scrollTop <= 0}
        >
          <ChevronUpIcon className="h-4 w-4" />
        </Button>
      </Tooltip>
      <Tooltip content="Bas">
        <Button
          variant="ghost"
          size="xs"
          className="h-7 w-7 p-0"
          onClick={() => scrollToBottom()}
          disabled={scrollTop >= maxScrollTop}
        >
          <ChevronDownIcon className="h-4 w-4" />
        </Button>
      </Tooltip>
      <div className="w-px h-6 bg-gray-200 dark:bg-gray-700" />
      <Tooltip content="Gauche">
        <Button
          variant="ghost"
          size="xs"
          className="h-7 w-7 p-0"
          onClick={() => scrollToLeft()}
          disabled={scrollLeft <= 0}
        >
          <ChevronLeftIcon className="h-4 w-4" />
        </Button>
      </Tooltip>
      <Tooltip content="Droite">
        <Button
          variant="ghost"
          size="xs"
          className="h-7 w-7 p-0"
          onClick={() => scrollToRight()}
          disabled={scrollLeft >= maxScrollLeft}
        >
          <ChevronRightIcon className="h-4 w-4" />
        </Button>
      </Tooltip>
      <div className="w-px h-6 bg-gray-200 dark:bg-gray-700" />
      <Tooltip content="Zoom avant">
        <Button
          variant="ghost"
          size="xs"
          className="h-7 w-7 p-0"
          onClick={zoomIn}
        >
          <PlusIcon className="h-4 w-4" />
        </Button>
      </Tooltip>
      <Tooltip content="Zoom arrière">
        <Button
          variant="ghost"
          size="xs"
          className="h-7 w-7 p-0"
          onClick={zoomOut}
        >
          <MinusIcon className="h-4 w-4" />
        </Button>
      </Tooltip>
      <Tooltip content="Réinitialiser le zoom">
        <Button
          variant="ghost"
          size="xs"
          className="h-7 w-7 p-0"
          onClick={resetZoom}
        >
          <ArrowsPointingOutIcon className="h-4 w-4" />
        </Button>
      </Tooltip>
      <span className="text-xs text-gray-500 dark:text-gray-400 min-w-[40px] text-center">
        {Math.round(zoom * 100)}%
      </span>
    </div>
  );
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const ScrollArea = forwardRef<HTMLDivElement, ScrollAreaProps>(
  (props, ref) => {
    const {
      // Contenu
      children,
      fallback,

      // Apparence
      variant = 'default',
      size = 'md',
      position = 'inside',
      visibility = 'auto',
      direction = 'vertical',
      barColor,
      trackColor,
      barThickness,
      barRadius,
      className,
      containerClassName,
      barClassName,
      trackClassName,

      // Comportement
      maxHeight = '100%',
      minHeight,
      maxWidth = '100%',
      minWidth,
      disabled = false,
      disableHorizontal = false,
      disableVertical = false,
      disableZoom = false,
      zoomFactor = 0.1,
      minZoom = 0.5,
      maxZoom = 2,
      defaultZoom = 1,
      snapType = 'none',
      snapAlign = 'start',
      snapStop = 'normal',

      // Contrôle du défilement
      scrollTop: externalScrollTop,
      scrollLeft: externalScrollLeft,
      onScroll,
      onScrollPosition,
      onScrollStart,
      onScrollEnd,
      onZoom,

      // Accessibilité
      ariaLabel = 'Zone de défilement',
      ariaDescribedby,
      id,
      role = 'region',

      // Avancé
      overflow = 'auto',
      padding,
      smoothScroll = true,
      scrollDuration = 300,
      hideDelay = 1000,
      disableDefaultStyles = false,
      observeContent = true,
      autoScroll = false,
      autoScrollOnMount = false,
      onLoad,
      viewportRef: externalViewportRef,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const viewportRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);
    const observerRef = useRef<ResizeObserver | null>(null);
    const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const hideTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const uniqueId = useId();
    const scrollId = id || `nexus-scroll-area-${uniqueId}`;

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [scrollTop, setScrollTop] = useState(0);
    const [scrollLeft, setScrollLeft] = useState(0);
    const [maxScrollTop, setMaxScrollTop] = useState(0);
    const [maxScrollLeft, setMaxScrollLeft] = useState(0);
    const [isScrolling, setIsScrolling] = useState(false);
    const [zoom, setZoom] = useState(defaultZoom);
    const [contentHeight, setContentHeight] = useState(0);
    const [contentWidth, setContentWidth] = useState(0);
    const [isMounted, setIsMounted] = useState(false);
    const [registeredAreas, setRegisteredAreas] = useState<Set<string>>(new Set());

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const isControlled = externalScrollTop !== undefined || externalScrollLeft !== undefined;
    const currentScrollTop = isControlled ? (externalScrollTop || 0) : scrollTop;
    const currentScrollLeft = isControlled ? (externalScrollLeft || 0) : scrollLeft;

    const hasVerticalScroll = maxScrollTop > 0 && !disableVertical;
    const hasHorizontalScroll = maxScrollLeft > 0 && !disableHorizontal;

    // ========================================================================
    // CALCUL DES MAX SCROLL
    // ========================================================================

    const updateMaxScroll = useCallback(() => {
      const viewport = viewportRef.current;
      const content = contentRef.current;
      if (!viewport || !content) return;

      const viewportRect = viewport.getBoundingClientRect();
      const contentRect = content.getBoundingClientRect();

      const newMaxScrollTop = Math.max(0, contentRect.height - viewportRect.height);
      const newMaxScrollLeft = Math.max(0, contentRect.width - viewportRect.width);

      setMaxScrollTop(newMaxScrollTop);
      setMaxScrollLeft(newMaxScrollLeft);

      setContentHeight(contentRect.height);
      setContentWidth(contentRect.width);
    }, []);

    // ========================================================================
    // SCROLL
    // ========================================================================

    const scrollTo = useCallback((top: number, left: number, smooth = smoothScroll) => {
      const viewport = viewportRef.current;
      if (!viewport) return;

      const newTop = Math.max(0, Math.min(maxScrollTop, top));
      const newLeft = Math.max(0, Math.min(maxScrollLeft, left));

      viewport.scrollTo({
        top: newTop,
        left: newLeft,
        behavior: smooth ? 'smooth' : 'auto',
      });

      if (isControlled) {
        if (onScrollPosition) onScrollPosition(newTop, newLeft);
      }
    }, [maxScrollTop, maxScrollLeft, smoothScroll, isControlled, onScrollPosition]);

    const scrollToTop = useCallback((smooth = true) => scrollTo(0, currentScrollLeft, smooth), [scrollTo, currentScrollLeft]);
    const scrollToBottom = useCallback((smooth = true) => scrollTo(maxScrollTop, currentScrollLeft, smooth), [scrollTo, maxScrollTop, currentScrollLeft]);
    const scrollToLeft = useCallback((smooth = true) => scrollTo(currentScrollTop, 0, smooth), [scrollTo, currentScrollTop]);
    const scrollToRight = useCallback((smooth = true) => scrollTo(currentScrollTop, maxScrollLeft, smooth), [scrollTo, currentScrollTop, maxScrollLeft]);

    // ========================================================================
    // ZOOM
    // ========================================================================

    const zoomIn = useCallback(() => {
      if (disableZoom) return;
      setZoom((prev) => {
        const newZoom = Math.min(maxZoom, prev + zoomFactor);
        onZoom?.(newZoom);
        return newZoom;
      });
    }, [disableZoom, maxZoom, zoomFactor, onZoom]);

    const zoomOut = useCallback(() => {
      if (disableZoom) return;
      setZoom((prev) => {
        const newZoom = Math.max(minZoom, prev - zoomFactor);
        onZoom?.(newZoom);
        return newZoom;
      });
    }, [disableZoom, minZoom, zoomFactor, onZoom]);

    const resetZoom = useCallback(() => {
      if (disableZoom) return;
      setZoom(defaultZoom);
      onZoom?.(defaultZoom);
    }, [disableZoom, defaultZoom, onZoom]);

    // ========================================================================
    // GESTION DES ÉVÉNEMENTS DE SCROLL
    // ========================================================================

    const handleScroll = useCallback((event: UIEvent<HTMLDivElement>) => {
      const target = event.currentTarget;
      const newScrollTop = target.scrollTop;
      const newScrollLeft = target.scrollLeft;

      if (!isControlled) {
        setScrollTop(newScrollTop);
        setScrollLeft(newScrollLeft);
      }

      if (onScroll) onScroll(event);
      if (onScrollPosition) onScrollPosition(newScrollTop, newScrollLeft);

      // Déclencher les événements de début/fin
      if (!isScrolling) {
        setIsScrolling(true);
        onScrollStart?.();
      }

      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }

      scrollTimeoutRef.current = setTimeout(() => {
        setIsScrolling(false);
        onScrollEnd?.();
      }, 150);
    }, [isControlled, onScroll, onScrollPosition, isScrolling, onScrollStart, onScrollEnd]);

    // ========================================================================
    // AUTO SCROLL
    // ========================================================================

    useEffect(() => {
      if (autoScroll && contentRef.current) {
        scrollToBottom();
      }
    }, [autoScroll, contentRef, scrollToBottom]);

    useEffect(() => {
      if (autoScrollOnMount && isMounted) {
        setTimeout(() => scrollToBottom(), 100);
      }
    }, [autoScrollOnMount, isMounted, scrollToBottom]);

    // ========================================================================
    // OBSERVER
    // ========================================================================

    useEffect(() => {
      if (!observeContent) return;

      const content = contentRef.current;
      if (!content) return;

      observerRef.current = new ResizeObserver(() => {
        updateMaxScroll();
      });

      observerRef.current.observe(content);

      return () => {
        if (observerRef.current) {
          observerRef.current.disconnect();
        }
      };
    }, [observeContent, updateMaxScroll]);

    // ========================================================================
    // HIDE DELAY
    // ========================================================================

    useEffect(() => {
      if (visibility !== 'auto') return;

      if (isScrolling) {
        if (hideTimeoutRef.current) {
          clearTimeout(hideTimeoutRef.current);
          hideTimeoutRef.current = null;
        }
      } else {
        hideTimeoutRef.current = setTimeout(() => {
          // Les barres seront cachées via CSS
        }, hideDelay);
      }

      return () => {
        if (hideTimeoutRef.current) {
          clearTimeout(hideTimeoutRef.current);
        }
      };
    }, [isScrolling, visibility, hideDelay]);

    // ========================================================================
    // MOUNT
    // ========================================================================

    useEffect(() => {
      setIsMounted(true);
      updateMaxScroll();
      onLoad?.();

      return () => {
        if (scrollTimeoutRef.current) {
          clearTimeout(scrollTimeoutRef.current);
        }
        if (hideTimeoutRef.current) {
          clearTimeout(hideTimeoutRef.current);
        }
      };
    }, [updateMaxScroll, onLoad]);

    // ========================================================================
    // CONTEXT
    // ========================================================================

    const contextValue = useMemo<ScrollAreaContextType>(
      () => ({
        scrollTop: currentScrollTop,
        scrollLeft: currentScrollLeft,
        maxScrollTop,
        maxScrollLeft,
        isScrolling,
        zoom,
        direction,
        size,
        variant,
        visibility,
        position,
        disabled,
        scrollTo,
        scrollToTop,
        scrollToBottom,
        scrollToLeft,
        scrollToRight,
        zoomIn,
        zoomOut,
        resetZoom,
        registerScrollArea: (id: string) => {
          setRegisteredAreas((prev) => new Set([...prev, id]));
        },
        unregisterScrollArea: (id: string) => {
          setRegisteredAreas((prev) => {
            const next = new Set(prev);
            next.delete(id);
            return next;
          });
        },
      }),
      [
        currentScrollTop,
        currentScrollLeft,
        maxScrollTop,
        maxScrollLeft,
        isScrolling,
        zoom,
        direction,
        size,
        variant,
        visibility,
        position,
        disabled,
        scrollTo,
        scrollToTop,
        scrollToBottom,
        scrollToLeft,
        scrollToRight,
        zoomIn,
        zoomOut,
        resetZoom,
      ]
    );

    // ========================================================================
    // RENDU DES BARRES
    // ========================================================================

    const renderScrollBars = () => {
      if (disabled) return null;

      return (
        <>
          {hasVerticalScroll && (
            <ScrollBar
              orientation="vertical"
              value={currentScrollTop}
              maxValue={maxScrollTop}
              size={size}
              variant={variant}
              visibility={visibility}
              position={position}
              barColor={barColor}
              trackColor={trackColor}
              barThickness={barThickness}
              barRadius={barRadius}
              isScrolling={isScrolling}
              disabled={disabled}
              className={barClassName}
              trackClassName={trackClassName}
              onScroll={(value) => scrollTo(value, currentScrollLeft)}
            />
          )}
          {hasHorizontalScroll && (
            <ScrollBar
              orientation="horizontal"
              value={currentScrollLeft}
              maxValue={maxScrollLeft}
              size={size}
              variant={variant}
              visibility={visibility}
              position={position}
              barColor={barColor}
              trackColor={trackColor}
              barThickness={barThickness}
              barRadius={barRadius}
              isScrolling={isScrolling}
              disabled={disabled}
              className={barClassName}
              trackClassName={trackClassName}
              onScroll={(value) => scrollTo(currentScrollTop, value)}
            />
          )}
        </>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const contentStyle: React.CSSProperties = {
      ...(zoom !== 1 && {
        transform: `scale(${zoom})`,
        transformOrigin: 'top left',
      }),
    };

    const containerStyle: React.CSSProperties = {
      ...(maxHeight && { maxHeight: maxHeight }),
      ...(minHeight && { minHeight: minHeight }),
      ...(maxWidth && { maxWidth: maxWidth }),
      ...(minWidth && { minWidth: minWidth }),
      ...(padding && { padding: padding }),
      ...(disableDefaultStyles ? {} : {
        position: 'relative',
        overflow: overflow,
      }),
    };

    const snapStyles = snapType !== 'none' ? {
      scrollSnapType: snapType === 'mandatory' ? 'y mandatory' : 'y proximity',
      scrollSnapAlign: snapAlign,
      scrollSnapStop: snapStop,
    } : {};

    return (
      <ScrollAreaContext.Provider value={contextValue}>
        <div
          ref={(node) => {
            if (typeof ref === 'function') ref(node);
            else if (ref) ref.current = node;
            containerRef.current = node;
          }}
          id={scrollId}
          className={cn(
            'relative',
            !disableDefaultStyles && 'overflow-hidden',
            className
          )}
          style={containerStyle}
          role={role}
          aria-label={ariaLabel}
          aria-describedby={ariaDescribedby}
        >
          {/* Vue principale */}
          <div
            ref={(node) => {
              viewportRef.current = node;
              if (externalViewportRef) {
                (externalViewportRef as React.MutableRefObject<HTMLDivElement>).current = node!;
              }
            }}
            className={cn(
              'h-full w-full',
              !disableDefaultStyles && 'overflow-auto overscroll-contain',
              containerClassName
            )}
            style={{
              ...snapStyles,
              scrollBehavior: smoothScroll ? 'smooth' : 'auto',
            }}
            onScroll={handleScroll}
            onWheel={(e) => {
              if (disabled) {
                e.preventDefault();
              }
            }}
          >
            {/* Contenu */}
            <div
              ref={contentRef}
              className={cn(
                'w-full',
                (direction === 'horizontal' || direction === 'both') && 'min-w-max'
              )}
              style={contentStyle}
            >
              {children}
            </div>
          </div>

          {/* Barres de défilement */}
          {renderScrollBars()}

          {/* Contrôles de navigation */}
          {!disabled && !disableVertical && !disableHorizontal && (
            <ScrollControls />
          )}

          {/* Fallback */}
          {fallback && !children && (
            <div className="flex items-center justify-center h-full w-full">
              {fallback}
            </div>
          )}
        </div>
      </ScrollAreaContext.Provider>
    );
  }
);

ScrollArea.displayName = 'ScrollArea';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- ScrollArea.Viewport ---
interface ScrollViewportProps {
  children: ReactNode;
  className?: string;
}

export const ScrollViewport: React.FC<ScrollViewportProps> = ({
  children,
  className,
}) => {
  return (
    <div className={cn('h-full w-full', className)}>
      {children}
    </div>
  );
};

// --- ScrollArea.Content ---
interface ScrollContentProps {
  children: ReactNode;
  className?: string;
}

export const ScrollContent: React.FC<ScrollContentProps> = ({
  children,
  className,
}) => {
  return (
    <div className={className}>
      {children}
    </div>
  );
};

// --- ScrollArea.Bar ---
interface ScrollBarCustomProps {
  orientation: 'vertical' | 'horizontal';
  className?: string;
}

export const ScrollBar: React.FC<ScrollBarCustomProps> = ({
  orientation,
  className,
}) => {
  return (
    <div
      className={cn(
        'absolute',
        orientation === 'vertical' ? 'right-0 top-0 h-full w-2' : 'bottom-0 left-0 h-2 w-full',
        className
      )}
    />
  );
};

// ============================================================================
// HOOKS
// ============================================================================

export const useScrollArea = () => {
  const context = useScrollAreaContext();
  return context;
};

export const useScrollTo = () => {
  const context = useScrollAreaContext();
  return {
    scrollTo: context.scrollTo,
    scrollToTop: context.scrollToTop,
    scrollToBottom: context.scrollToBottom,
    scrollToLeft: context.scrollToLeft,
    scrollToRight: context.scrollToRight,
  };
};

export const useScrollPosition = () => {
  const context = useScrollAreaContext();
  return {
    scrollTop: context.scrollTop,
    scrollLeft: context.scrollLeft,
    maxScrollTop: context.maxScrollTop,
    maxScrollLeft: context.maxScrollLeft,
  };
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(ScrollArea, {
  Viewport: ScrollViewport,
  Content: ScrollContent,
  Bar: ScrollBar,
});

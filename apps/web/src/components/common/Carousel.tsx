/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import { cn } from '@/utils/helpers';
import { Button } from './Button';
import { ChevronLeft, ChevronRight, Dot } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface CarouselProps
  extends React.HTMLAttributes<HTMLDivElement> {
  autoPlay?: boolean;
  autoPlayInterval?: number;
  infinite?: boolean;
  showIndicators?: boolean;
  showArrows?: boolean;
  showDots?: boolean;
  dotPosition?: 'bottom' | 'top' | 'left' | 'right';
  dotSize?: 'sm' | 'md' | 'lg';
  arrowPosition?: 'inside' | 'outside';
  arrowSize?: 'sm' | 'md' | 'lg';
  onSlideChange?: (index: number) => void;
  initialSlide?: number;
  slidesPerView?: number;
  gap?: number;
  children: React.ReactNode;
  className?: string;
}

export interface CarouselContentProps
  extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export interface CarouselItemProps
  extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  index?: number;
}

export interface CarouselPreviousProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {}

export interface CarouselNextProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {}

// ============================================
// CONTEXTE
// ============================================

interface CarouselContextType {
  currentIndex: number;
  totalSlides: number;
  goTo: (index: number) => void;
  goToPrev: () => void;
  goToNext: () => void;
  isPlaying: boolean;
  togglePlay: () => void;
  slidesPerView: number;
  gap: number;
  registerSlide: (index: number) => void;
  unregisterSlide: (index: number) => void;
}

const CarouselContext = React.createContext<CarouselContextType | undefined>(
  undefined
);

const useCarousel = () => {
  const context = React.useContext(CarouselContext);
  if (!context) {
    throw new Error('useCarousel must be used within a Carousel');
  }
  return context;
};

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

const Carousel = React.forwardRef<HTMLDivElement, CarouselProps>(
  (
    {
      autoPlay = false,
      autoPlayInterval = 3000,
      infinite = true,
      showIndicators = true,
      showArrows = true,
      showDots = true,
      dotPosition = 'bottom',
      dotSize = 'md',
      arrowPosition = 'inside',
      arrowSize = 'md',
      onSlideChange,
      initialSlide = 0,
      slidesPerView = 1,
      gap = 0,
      children,
      className,
      ...props
    },
    ref
  ) => {
    // ============================================
    // RÉFÉRENCES
    // ============================================
    const containerRef = React.useRef<HTMLDivElement>(null);
    const timerRef = React.useRef<NodeJS.Timeout | null>(null);

    // ============================================
    // ÉTATS
    // ============================================
    const [currentIndex, setCurrentIndex] = React.useState(initialSlide);
    const [totalSlides, setTotalSlides] = React.useState(0);
    const [isPlaying, setIsPlaying] = React.useState(autoPlay);
    const [isTransitioning, setIsTransitioning] = React.useState(false);
    const [slidesRegistry, setSlidesRegistry] = React.useState<Set<number>>(
      new Set()
    );

    // ============================================
    // FONCTIONS
    // ============================================

    const goTo = React.useCallback(
      (index: number) => {
        if (isTransitioning) return;

        let targetIndex = index;

        if (infinite) {
          if (targetIndex < 0) {
            targetIndex = totalSlides - 1;
          } else if (targetIndex >= totalSlides) {
            targetIndex = 0;
          }
        } else {
          targetIndex = Math.max(0, Math.min(targetIndex, totalSlides - 1));
        }

        if (targetIndex === currentIndex) return;

        setIsTransitioning(true);
        setCurrentIndex(targetIndex);
        onSlideChange?.(targetIndex);

        setTimeout(() => {
          setIsTransitioning(false);
        }, 500);
      },
      [currentIndex, totalSlides, infinite, isTransitioning, onSlideChange]
    );

    const goToPrev = React.useCallback(() => {
      goTo(currentIndex - 1);
    }, [currentIndex, goTo]);

    const goToNext = React.useCallback(() => {
      goTo(currentIndex + 1);
    }, [currentIndex, goTo]);

    const registerSlide = React.useCallback((index: number) => {
      setSlidesRegistry((prev) => {
        const newSet = new Set(prev);
        newSet.add(index);
        return newSet;
      });
    }, []);

    const unregisterSlide = React.useCallback((index: number) => {
      setSlidesRegistry((prev) => {
        const newSet = new Set(prev);
        newSet.delete(index);
        return newSet;
      });
    }, []);

    const togglePlay = React.useCallback(() => {
      setIsPlaying((prev) => !prev);
    }, []);

    // ============================================
    // EFFETS
    // ============================================

    React.useEffect(() => {
      setTotalSlides(slidesRegistry.size);
    }, [slidesRegistry]);

    React.useEffect(() => {
      if (autoPlay && isPlaying) {
        timerRef.current = setInterval(goToNext, autoPlayInterval);
      } else if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }

      return () => {
        if (timerRef.current) {
          clearInterval(timerRef.current);
          timerRef.current = null;
        }
      };
    }, [autoPlay, isPlaying, autoPlayInterval, goToNext]);

    React.useEffect(() => {
      if (initialSlide !== currentIndex) {
        setCurrentIndex(initialSlide);
      }
    }, [initialSlide]);

    // ============================================
    // CONTEXTE
    // ============================================

    const contextValue = React.useMemo(
      () => ({
        currentIndex,
        totalSlides,
        goTo,
        goToPrev,
        goToNext,
        isPlaying,
        togglePlay,
        slidesPerView,
        gap,
        registerSlide,
        unregisterSlide,
      }),
      [
        currentIndex,
        totalSlides,
        goTo,
        goToPrev,
        goToNext,
        isPlaying,
        togglePlay,
        slidesPerView,
        gap,
        registerSlide,
        unregisterSlide,
      ]
    );

    // ============================================
    // RENDU
    // ============================================

    const dotSizes = {
      sm: 'h-1.5 w-1.5',
      md: 'h-2 w-2',
      lg: 'h-2.5 w-2.5',
    };

    const arrowSizes = {
      sm: 'h-6 w-6',
      md: 'h-8 w-8',
      lg: 'h-10 w-10',
    };

    return (
      <CarouselContext.Provider value={contextValue}>
        <div
          ref={ref}
          className={cn('relative group', className)}
          {...props}
        >
          {/* Conteneur du carrousel */}
          <div
            ref={containerRef}
            className="relative overflow-hidden rounded-lg"
          >
            {children}
          </div>

          {/* Flèches */}
          {showArrows && totalSlides > 1 && (
            <>
              <Button
                variant="outline"
                size="sm"
                className={cn(
                  'absolute top-1/2 -translate-y-1/2 z-10 rounded-full p-0',
                  'bg-white/80 hover:bg-white dark:bg-gray-800/80 dark:hover:bg-gray-800',
                  'border-gray-200 dark:border-gray-700',
                  'transition-all duration-200',
                  'opacity-0 group-hover:opacity-100',
                  arrowPosition === 'inside' ? 'left-2' : '-left-4',
                  arrowSizes[arrowSize]
                )}
                onClick={goToPrev}
                disabled={!infinite && currentIndex === 0}
                aria-label="Précédent"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className={cn(
                  'absolute top-1/2 -translate-y-1/2 z-10 rounded-full p-0',
                  'bg-white/80 hover:bg-white dark:bg-gray-800/80 dark:hover:bg-gray-800',
                  'border-gray-200 dark:border-gray-700',
                  'transition-all duration-200',
                  'opacity-0 group-hover:opacity-100',
                  arrowPosition === 'inside' ? 'right-2' : '-right-4',
                  arrowSizes[arrowSize]
                )}
                onClick={goToNext}
                disabled={!infinite && currentIndex === totalSlides - 1}
                aria-label="Suivant"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </>
          )}

          {/* Dots / Indicateurs */}
          {showDots && totalSlides > 1 && (
            <div
              className={cn(
                'absolute flex items-center justify-center gap-1.5 z-10',
                dotPosition === 'bottom' && 'bottom-4 left-1/2 -translate-x-1/2',
                dotPosition === 'top' && 'top-4 left-1/2 -translate-x-1/2',
                dotPosition === 'left' && 'left-4 top-1/2 -translate-y-1/2 flex-col',
                dotPosition === 'right' && 'right-4 top-1/2 -translate-y-1/2 flex-col'
              )}
            >
              {Array.from({ length: totalSlides }).map((_, index) => (
                <button
                  key={index}
                  className={cn(
                    'rounded-full transition-all duration-200',
                    dotSizes[dotSize],
                    index === currentIndex
                      ? 'bg-blue-600 w-6 dark:bg-blue-400'
                      : 'bg-gray-300 hover:bg-gray-400 dark:bg-gray-600 dark:hover:bg-gray-500'
                  )}
                  onClick={() => goTo(index)}
                  aria-label={`Aller à la slide ${index + 1}`}
                />
              ))}
            </div>
          )}

          {/* Indicateurs (compteur) */}
          {showIndicators && totalSlides > 1 && (
            <div className="absolute bottom-4 right-4 z-10 rounded-full bg-black/50 px-3 py-1 text-xs text-white backdrop-blur-sm">
              {currentIndex + 1} / {totalSlides}
            </div>
          )}
        </div>
      </CarouselContext.Provider>
    );
  }
);
Carousel.displayName = 'Carousel';

// ============================================
// SOUS-COMPOSANTS
// ============================================

const CarouselContent = React.forwardRef<
  HTMLDivElement,
  CarouselContentProps
>(({ className, children, ...props }, ref) => {
  const { currentIndex, slidesPerView, gap } = useCarousel();

  const childrenArray = React.Children.toArray(children);
  const totalSlides = childrenArray.length;

  return (
    <div
      ref={ref}
      className={cn('flex transition-transform duration-500 ease-in-out', className)}
      style={{
        transform: `translateX(-${(currentIndex * 100) / slidesPerView}%)`,
        gap: `${gap}px`,
      }}
      {...props}
    >
      {childrenArray.map((child, index) => (
        <div
          key={index}
          className="flex-shrink-0"
          style={{
            width: `${100 / slidesPerView}%`,
          }}
        >
          {child}
        </div>
      ))}
    </div>
  );
});
CarouselContent.displayName = 'CarouselContent';

const CarouselItem = React.forwardRef<HTMLDivElement, CarouselItemProps>(
  ({ className, children, index, ...props }, ref) => {
    const { registerSlide, unregisterSlide } = useCarousel();

    React.useEffect(() => {
      if (index !== undefined) {
        registerSlide(index);
        return () => unregisterSlide(index);
      }
    }, [index, registerSlide, unregisterSlide]);

    return (
      <div
        ref={ref}
        className={cn('flex-shrink-0', className)}
        {...props}
      >
        {children}
      </div>
    );
  }
);
CarouselItem.displayName = 'CarouselItem';

const CarouselPrevious = React.forwardRef<
  HTMLButtonElement,
  CarouselPreviousProps
>(({ className, ...props }, ref) => {
  const { goToPrev } = useCarousel();

  return (
    <Button
      ref={ref}
      variant="outline"
      size="sm"
      className={cn(
        'absolute left-2 top-1/2 -translate-y-1/2 z-10 rounded-full p-0 h-8 w-8',
        className
      )}
      onClick={goToPrev}
      {...props}
    >
      <ChevronLeft className="h-4 w-4" />
    </Button>
  );
});
CarouselPrevious.displayName = 'CarouselPrevious';

const CarouselNext = React.forwardRef<
  HTMLButtonElement,
  CarouselNextProps
>(({ className, ...props }, ref) => {
  const { goToNext } = useCarousel();

  return (
    <Button
      ref={ref}
      variant="outline"
      size="sm"
      className={cn(
        'absolute right-2 top-1/2 -translate-y-1/2 z-10 rounded-full p-0 h-8 w-8',
        className
      )}
      onClick={goToNext}
      {...props}
    >
      <ChevronRight className="h-4 w-4" />
    </Button>
  );
});
CarouselNext.displayName = 'CarouselNext';

// ============================================
// EXPORTATIONS
// ============================================

export {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselPrevious,
  CarouselNext,
};

export default Carousel;

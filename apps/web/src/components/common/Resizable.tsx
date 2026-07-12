// apps/web/src/components/common/Resizable.tsx
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
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence, MotionConfig } from 'framer-motion';
import {
  GripVerticalIcon,
  GripHorizontalIcon,
  Maximize2Icon,
  Minimize2Icon,
  PanelLeftCloseIcon,
  PanelLeftOpenIcon,
  PanelRightCloseIcon,
  PanelRightOpenIcon,
  PanelTopCloseIcon,
  PanelTopOpenIcon,
  PanelBottomCloseIcon,
  PanelBottomOpenIcon,
  XIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  RotateCwIcon,
  RotateCcwIcon,
} from 'lucide-react';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';

// ============================================================================
// TYPES
// ============================================================================

export type ResizableDirection = 'horizontal' | 'vertical' | 'both';
export type ResizableHandlePosition = 'left' | 'right' | 'top' | 'bottom' | 'corner';
export type ResizableSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type ResizableVariant = 'default' | 'minimal' | 'solid' | 'outlined' | 'ghost';
export type ResizableSnapMode = 'none' | 'proximity' | 'always';

export interface ResizablePanel {
  /** Identifiant unique du panneau */
  id: string;
  /** Contenu du panneau */
  content: ReactNode;
  /** Taille initiale en pixels ou pourcentage */
  defaultSize?: number | string;
  /** Taille minimale en pixels */
  minSize?: number;
  /** Taille maximale en pixels */
  maxSize?: number;
  /** Si le panneau est collapsible */
  collapsible?: boolean;
  /** Taille réduite en pixels */
  collapsedSize?: number;
  /** Si le panneau est visible */
  visible?: boolean;
  /** Classes additionnelles */
  className?: string;
}

export interface ResizableProps {
  // --- Panneaux ---
  /** Panneaux à redimensionner */
  panels: ResizablePanel[];
  /** Direction du redimensionnement */
  direction?: ResizableDirection;
  /** Panneau actif par défaut */
  defaultActivePanel?: string;
  /** Panneau actif (contrôlé) */
  activePanel?: string;
  /** Callback lors du changement de panneau actif */
  onActivePanelChange?: (panelId: string) => void;

  // --- Apparence ---
  /** Variante d'affichage */
  variant?: ResizableVariant;
  /** Taille des poignées */
  size?: ResizableSize;
  /** Couleur des poignées */
  handleColor?: string;
  /** Épaisseur des poignées */
  handleThickness?: number;
  /** Longueur des poignées */
  handleLength?: number;
  /** Afficher les poignées */
  showHandles?: boolean;
  /** Afficher les icônes de redimensionnement */
  showIcons?: boolean;
  /** Afficher les boutons de collapse */
  showCollapseButtons?: boolean;
  /** Afficher les boutons de maximisation */
  showMaximizeButtons?: boolean;
  /** Classes additionnelles */
  className?: string;
  /** Classes pour les poignées */
  handleClassName?: string;
  /** Classes pour les panneaux */
  panelClassName?: string;

  // --- Comportement ---
  /** Désactiver le redimensionnement */
  disabled?: boolean;
  /** Mode d'accrochage */
  snapMode?: ResizableSnapMode;
  /** Valeurs d'accrochage */
  snapPoints?: number[];
  /** Seuil d'accrochage */
  snapThreshold?: number;
  /** Délai avant la mise à jour (ms) */
  updateDelay?: number;
  /** Animation du redimensionnement */
  animate?: boolean;
  /** Durée de l'animation (ms) */
  animationDuration?: number;
  /** Persistance des tailles */
  persistSizes?: boolean;
  /** Clé de persistance */
  persistKey?: string;

  // --- Événements ---
  /** Callback lors du début du redimensionnement */
  onResizeStart?: (panelId: string) => void;
  /** Callback pendant le redimensionnement */
  onResize?: (sizes: Record<string, number>) => void;
  /** Callback à la fin du redimensionnement */
  onResizeEnd?: (sizes: Record<string, number>) => void;
  /** Callback lors du collapse */
  onCollapse?: (panelId: string, collapsed: boolean) => void;
  /** Callback lors du maximize */
  onMaximize?: (panelId: string, maximized: boolean) => void;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Container des panneaux */
  containerRef?: React.RefObject<HTMLDivElement>;
  /** Largeur totale fixe */
  fixedWidth?: number;
  /** Hauteur totale fixe */
  fixedHeight?: number;
  /** Espacement entre les panneaux */
  gutterSize?: number;
}

// ============================================================================
// CONTEXT
// ============================================================================

interface ResizableContextType {
  direction: ResizableDirection;
  variant: ResizableVariant;
  size: ResizableSize;
  disabled: boolean;
  animate: boolean;
  animationDuration: number;
  showHandles: boolean;
  showIcons: boolean;
  showCollapseButtons: boolean;
  showMaximizeButtons: boolean;
  handleThickness: number;
  handleLength: number;
  handleColor?: string;
  activePanel: string | null;
  setActivePanel: (panelId: string | null) => void;
  panelSizes: Record<string, number>;
  setPanelSize: (panelId: string, size: number) => void;
  toggleCollapse: (panelId: string) => void;
  toggleMaximize: (panelId: string) => void;
  isCollapsed: (panelId: string) => boolean;
  isMaximized: (panelId: string) => boolean;
  registerPanel: (panelId: string) => void;
  unregisterPanel: (panelId: string) => void;
}

const ResizableContext = createContext<ResizableContextType | null>(null);

export const useResizableContext = () => {
  const context = useContext(ResizableContext);
  if (!context) {
    throw new Error('useResizableContext must be used within a Resizable');
  }
  return context;
};

// ============================================================================
// COMPOSANTS INTERNES
// ============================================================================

// --- Poignée de redimensionnement ---
interface ResizeHandleProps {
  position: ResizableHandlePosition;
  panelId: string;
  className?: string;
  onResizeStart: (e: React.MouseEvent | React.TouchEvent, panelId: string) => void;
}

const ResizeHandle: React.FC<ResizeHandleProps> = ({
  position,
  panelId,
  className,
  onResizeStart,
}) => {
  const context = useResizableContext();
  const {
    direction,
    variant,
    size,
    disabled,
    showIcons,
    handleThickness,
    handleLength,
    handleColor,
    showHandles,
    handleClassName,
  } = context;

  const isHorizontal = direction === 'horizontal';
  const isVertical = direction === 'vertical';
  const isBoth = direction === 'both';

  // Variante des poignées
  const variantClasses = {
    default: 'bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600',
    minimal: 'bg-transparent hover:bg-gray-200 dark:hover:bg-gray-700',
    solid: 'bg-gray-300 dark:bg-gray-600 hover:bg-gray-400 dark:hover:bg-gray-500',
    outlined: 'border-2 border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 bg-transparent',
    ghost: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800',
  };

  // Taille des poignées
  const sizeMap = {
    xs: { handle: 'p-0.5', icon: 'h-3 w-3' },
    sm: { handle: 'p-1', icon: 'h-3.5 w-3.5' },
    md: { handle: 'p-1.5', icon: 'h-4 w-4' },
    lg: { handle: 'p-2', icon: 'h-5 w-5' },
    xl: { handle: 'p-2.5', icon: 'h-6 w-6' },
  };

  // Position et orientation
  const isLeft = position === 'left';
  const isRight = position === 'right';
  const isTop = position === 'top';
  const isBottom = position === 'bottom';
  const isCorner = position === 'corner';

  const isHorizontalHandle = isLeft || isRight;
  const isVerticalHandle = isTop || isBottom;

  const handleStyles: React.CSSProperties = {
    ...(handleThickness && {
      [isHorizontalHandle ? 'width' : 'height']: handleThickness,
      [isHorizontalHandle ? 'height' : 'width']: handleLength || '100%',
    }),
    ...(handleColor && { backgroundColor: handleColor }),
  };

  // Déterminer le curseur
  const cursorMap = {
    left: 'ew-resize',
    right: 'ew-resize',
    top: 'ns-resize',
    bottom: 'ns-resize',
    corner: 'nwse-resize',
  };

  // Gestionnaires d'événements tactiles
  const handleTouchStart = (e: React.TouchEvent) => {
    e.preventDefault();
    onResizeStart(e, panelId);
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    onResizeStart(e, panelId);
  };

  if (!showHandles) return null;

  // Rendu du grip
  const renderGrip = () => {
    if (!showIcons) return null;

    const iconClass = sizeMap[size]?.icon || 'h-4 w-4';

    if (isHorizontalHandle) {
      return <GripVerticalIcon className={cn('text-gray-400', iconClass)} />;
    }
    if (isVerticalHandle) {
      return <GripHorizontalIcon className={cn('text-gray-400', iconClass)} />;
    }
    if (isCorner) {
      return (
        <div className="flex items-center gap-0.5">
          <GripVerticalIcon className={cn('text-gray-400', iconClass)} />
          <GripHorizontalIcon className={cn('text-gray-400', iconClass)} />
        </div>
      );
    }
    return null;
  };

  // Position des poignées
  const positionClasses = {
    left: 'left-0 -translate-x-1/2 cursor-ew-resize',
    right: 'right-0 translate-x-1/2 cursor-ew-resize',
    top: 'top-0 -translate-y-1/2 cursor-ns-resize',
    bottom: 'bottom-0 translate-y-1/2 cursor-ns-resize',
    corner: 'bottom-0 right-0 cursor-nwse-resize',
  };

  return (
    <div
      className={cn(
        'absolute z-10 flex items-center justify-center touch-none select-none transition-colors',
        isHorizontalHandle && 'flex-col',
        isVerticalHandle && 'flex-row',
        isCorner && 'flex-col',
        positionClasses[position],
        variantClasses[variant] || variantClasses.default,
        sizeMap[size]?.handle,
        disabled && 'opacity-30 cursor-not-allowed',
        handleClassName,
        className
      )}
      style={handleStyles}
      onMouseDown={handleMouseDown}
      onTouchStart={handleTouchStart}
      role="separator"
      aria-orientation={isHorizontalHandle ? 'horizontal' : 'vertical'}
      aria-label={`Redimensionner le panneau`}
    >
      {renderGrip()}
    </div>
  );
};

// --- Boutons de contrôle du panneau ---
interface PanelControlsProps {
  panelId: string;
  className?: string;
}

const PanelControls: React.FC<PanelControlsProps> = ({ panelId, className }) => {
  const context = useResizableContext();
  const {
    showCollapseButtons,
    showMaximizeButtons,
    isCollapsed,
    isMaximized,
    toggleCollapse,
    toggleMaximize,
  } = context;

  const collapsed = isCollapsed(panelId);
  const maximized = isMaximized(panelId);

  if (!showCollapseButtons && !showMaximizeButtons) return null;

  return (
    <div className={cn('flex items-center gap-0.5', className)}>
      {showCollapseButtons && (
        <Tooltip content={collapsed ? 'Développer' : 'Réduire'}>
          <Button
            variant="ghost"
            size="xs"
            className="h-6 w-6 p-0"
            onClick={() => toggleCollapse(panelId)}
          >
            {collapsed ? (
              <PanelLeftOpenIcon className="h-3.5 w-3.5" />
            ) : (
              <PanelLeftCloseIcon className="h-3.5 w-3.5" />
            )}
          </Button>
        </Tooltip>
      )}
      {showMaximizeButtons && (
        <Tooltip content={maximized ? 'Restaurer' : 'Agrandir'}>
          <Button
            variant="ghost"
            size="xs"
            className="h-6 w-6 p-0"
            onClick={() => toggleMaximize(panelId)}
          >
            {maximized ? (
              <Minimize2Icon className="h-3.5 w-3.5" />
            ) : (
              <Maximize2Icon className="h-3.5 w-3.5" />
            )}
          </Button>
        </Tooltip>
      )}
    </div>
  );
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const Resizable = forwardRef<HTMLDivElement, ResizableProps>(
  (props, ref) => {
    const {
      // Panneaux
      panels,
      direction = 'horizontal',
      defaultActivePanel,
      activePanel: externalActivePanel,
      onActivePanelChange,

      // Apparence
      variant = 'default',
      size = 'md',
      handleColor,
      handleThickness,
      handleLength = 40,
      showHandles = true,
      showIcons = true,
      showCollapseButtons = true,
      showMaximizeButtons = true,
      className,
      handleClassName,
      panelClassName,

      // Comportement
      disabled = false,
      snapMode = 'none',
      snapPoints = [],
      snapThreshold = 20,
      updateDelay = 16,
      animate = true,
      animationDuration = 200,
      persistSizes = false,
      persistKey,

      // Événements
      onResizeStart,
      onResize,
      onResizeEnd,
      onCollapse,
      onMaximize,

      // Accessibilité
      ariaLabel = 'Panneaux redimensionnables',
      id,

      // Avancé
      containerRef: externalContainerRef,
      fixedWidth,
      fixedHeight,
      gutterSize = 4,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const activeResizeRef = useRef<{
      panelId: string;
      startX: number;
      startY: number;
      startSize: number;
      direction: ResizableDirection;
    } | null>(null);
    const animationFrameRef = useRef<number | null>(null);
    const uniqueId = useId();
    const resizableId = id || `nexus-resizable-${uniqueId}`;

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [panelSizes, setPanelSizes] = useState<Record<string, number>>(() => {
      // Initialiser les tailles
      const initial: Record<string, number> = {};
      let total = 0;
      const visiblePanels = panels.filter((p) => p.visible !== false);

      // Charger depuis la persistance
      if (persistSizes && persistKey) {
        try {
          const saved = localStorage.getItem(`resizable-${persistKey}`);
          if (saved) {
            const parsed = JSON.parse(saved);
            visiblePanels.forEach((panel) => {
              if (parsed[panel.id] !== undefined) {
                initial[panel.id] = parsed[panel.id];
              }
            });
          }
        } catch (e) {
          // Ignorer les erreurs de persistance
        }
      }

      // Définir les tailles par défaut pour les panneaux sans taille
      const remainingPanels = visiblePanels.filter((p) => initial[p.id] === undefined);
      const defaultSizePerPanel = remainingPanels.length > 0
        ? (fixedWidth || containerRef.current?.clientWidth || 800) / remainingPanels.length
        : 0;

      remainingPanels.forEach((panel) => {
        initial[panel.id] = typeof panel.defaultSize === 'number'
          ? panel.defaultSize
          : defaultSizePerPanel;
      });

      return initial;
    });

    const [activePanel, setActivePanel] = useState<string | null>(
      externalActivePanel || defaultActivePanel || panels[0]?.id || null
    );
    const [maximizedPanel, setMaximizedPanel] = useState<string | null>(null);
    const [isResizing, setIsResizing] = useState(false);
    const [panelStates, setPanelStates] = useState<Record<string, { collapsed: boolean }>>(() => {
      const states: Record<string, { collapsed: boolean }> = {};
      panels.forEach((panel) => {
        states[panel.id] = { collapsed: false };
      });
      return states;
    });

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const isControlled = externalActivePanel !== undefined;
    const currentActivePanel = isControlled ? externalActivePanel : activePanel;
    const visiblePanels = panels.filter(
      (p) => p.visible !== false && !panelStates[p.id]?.collapsed
    );

    const totalSize = useMemo(() => {
      let total = 0;
      visiblePanels.forEach((panel) => {
        total += panelSizes[panel.id] || 0;
      });
      return total;
    }, [visiblePanels, panelSizes]);

    const isBoth = direction === 'both';

    // ========================================================================
    // PERSISTANCE
    // ========================================================================

    useEffect(() => {
      if (persistSizes && persistKey) {
        localStorage.setItem(`resizable-${persistKey}`, JSON.stringify(panelSizes));
      }
    }, [panelSizes, persistSizes, persistKey]);

    // ========================================================================
    // REDIMENSIONNEMENT
    // ========================================================================

    const startResize = useCallback((
      e: React.MouseEvent | React.TouchEvent,
      panelId: string
    ) => {
      if (disabled) return;

      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;

      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
      const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;

      activeResizeRef.current = {
        panelId,
        startX: clientX,
        startY: clientY,
        startSize: panelSizes[panelId] || 0,
        direction,
      };

      setIsResizing(true);
      onResizeStart?.(panelId);

      // Prévenir la sélection
      document.body.style.userSelect = 'none';
      document.body.style.cursor = direction === 'horizontal' ? 'ew-resize' : 'ns-resize';
    }, [disabled, direction, panelSizes, onResizeStart]);

    const updateResize = useCallback((e: MouseEvent | TouchEvent) => {
      if (!activeResizeRef.current || !containerRef.current) return;

      const { panelId, startX, startY, startSize } = activeResizeRef.current;

      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
      const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;

      const deltaX = clientX - startX;
      const deltaY = clientY - startY;

      let newSize = startSize;

      if (direction === 'horizontal' || isBoth) {
        newSize += deltaX;
      }
      if (direction === 'vertical' || isBoth) {
        newSize += deltaY;
      }

      // Appliquer les limites
      const panel = panels.find((p) => p.id === panelId);
      if (panel) {
        const minSize = panel.minSize || 50;
        const maxSize = panel.maxSize || Infinity;
        newSize = Math.max(minSize, Math.min(maxSize, newSize));
      }

      // Accrochage
      if (snapMode !== 'none' && snapPoints.length > 0) {
        const threshold = snapThreshold || 20;
        let snapped = false;
        for (const point of snapPoints) {
          if (Math.abs(newSize - point) < threshold) {
            newSize = point;
            snapped = true;
            break;
          }
        }
        if (snapMode === 'always' && !snapped) {
          // Trouver le point le plus proche
          let closest = snapPoints[0];
          let closestDist = Infinity;
          for (const point of snapPoints) {
            const dist = Math.abs(newSize - point);
            if (dist < closestDist) {
              closestDist = dist;
              closest = point;
            }
          }
          newSize = closest;
        }
      }

      // Mise à jour avec animation
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }

      if (updateDelay > 0) {
        animationFrameRef.current = requestAnimationFrame(() => {
          setPanelSizes((prev) => {
            const updated = { ...prev, [panelId]: newSize };
            onResize?.(updated);
            return updated;
          });
        });
      } else {
        setPanelSizes((prev) => {
          const updated = { ...prev, [panelId]: newSize };
          onResize?.(updated);
          return updated;
        });
      }
    }, [direction, isBoth, panels, snapMode, snapPoints, snapThreshold, updateDelay, onResize]);

    const endResize = useCallback(() => {
      if (!activeResizeRef.current) return;

      const panelId = activeResizeRef.current.panelId;
      activeResizeRef.current = null;
      setIsResizing(false);

      document.body.style.userSelect = '';
      document.body.style.cursor = '';

      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }

      onResizeEnd?.(panelSizes);
    }, [panelSizes, onResizeEnd]);

    // ========================================================================
    // ÉVÉNEMENTS GLOBAUX
    // ========================================================================

    useEffect(() => {
      if (!isResizing) return;

      const handleMouseMove = (e: MouseEvent) => updateResize(e);
      const handleTouchMove = (e: TouchEvent) => updateResize(e);
      const handleEnd = () => endResize();

      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleEnd);
      window.addEventListener('touchmove', handleTouchMove, { passive: false });
      window.addEventListener('touchend', handleEnd);

      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleEnd);
        window.removeEventListener('touchmove', handleTouchMove);
        window.removeEventListener('touchend', handleEnd);
      };
    }, [isResizing, updateResize, endResize]);

    // ========================================================================
    // COLLAPSE / MAXIMIZE
    // ========================================================================

    const toggleCollapse = useCallback((panelId: string) => {
      setPanelStates((prev) => {
        const isCollapsed = prev[panelId]?.collapsed || false;
        const newState = {
          ...prev,
          [panelId]: { collapsed: !isCollapsed },
        };

        // Si on collapse un panneau, on le retire du maximized
        if (!isCollapsed && maximizedPanel === panelId) {
          setMaximizedPanel(null);
        }

        onCollapse?.(panelId, !isCollapsed);
        return newState;
      });
    }, [maximizedPanel, onCollapse]);

    const toggleMaximize = useCallback((panelId: string) => {
      setMaximizedPanel((prev) => {
        const isMaximized = prev === panelId;
        const newMaximized = isMaximized ? null : panelId;

        // Si on maximise, on s'assure que le panneau n'est pas collapsé
        if (!isMaximized) {
          setPanelStates((states) => ({
            ...states,
            [panelId]: { collapsed: false },
          }));
        }

        onMaximize?.(panelId, !isMaximized);
        return newMaximized;
      });
    }, [onMaximize]);

    const isCollapsed = useCallback((panelId: string) => {
      return panelStates[panelId]?.collapsed || false;
    }, [panelStates]);

    const isMaximized = useCallback((panelId: string) => {
      return maximizedPanel === panelId;
    }, [maximizedPanel]);

    // ========================================================================
    // CONTEXT
    // ========================================================================

    const contextValue = useMemo<ResizableContextType>(
      () => ({
        direction,
        variant,
        size,
        disabled,
        animate,
        animationDuration,
        showHandles,
        showIcons,
        showCollapseButtons,
        showMaximizeButtons,
        handleThickness: handleThickness || (direction === 'horizontal' ? 6 : 6),
        handleLength,
        handleColor,
        activePanel: currentActivePanel,
        setActivePanel: (panelId: string | null) => {
          if (isControlled) {
            onActivePanelChange?.(panelId || '');
          } else {
            setActivePanel(panelId);
          }
        },
        panelSizes,
        setPanelSize: (panelId: string, size: number) => {
          setPanelSizes((prev) => ({ ...prev, [panelId]: size }));
        },
        toggleCollapse,
        toggleMaximize,
        isCollapsed,
        isMaximized,
        registerPanel: () => {},
        unregisterPanel: () => {},
      }),
      [
        direction,
        variant,
        size,
        disabled,
        animate,
        animationDuration,
        showHandles,
        showIcons,
        showCollapseButtons,
        showMaximizeButtons,
        handleThickness,
        handleLength,
        handleColor,
        currentActivePanel,
        isControlled,
        onActivePanelChange,
        panelSizes,
        toggleCollapse,
        toggleMaximize,
        isCollapsed,
        isMaximized,
      ]
    );

    // ========================================================================
    // CALCUL DES TAILLES
    // ========================================================================

    const getPanelStyle = useCallback((panel: ResizablePanel) => {
      const isCollapsedState = panelStates[panel.id]?.collapsed || false;
      const isMaximizedState = maximizedPanel === panel.id;
      const size = panelSizes[panel.id] || 0;

      const styles: React.CSSProperties = {};

      if (isMaximizedState) {
        styles.flex = '1 1 100%';
        styles.width = '100%';
        styles.height = '100%';
      } else if (isCollapsedState) {
        const collapsedSize = panel.collapsedSize || 0;
        if (direction === 'horizontal' || isBoth) {
          styles.width = collapsedSize;
          styles.flex = `0 0 ${collapsedSize}px`;
        }
        if (direction === 'vertical' || isBoth) {
          styles.height = collapsedSize;
          styles.flex = `0 0 ${collapsedSize}px`;
        }
        styles.overflow = 'hidden';
      } else {
        if (direction === 'horizontal' || isBoth) {
          styles.width = size;
          styles.flex = `0 0 ${size}px`;
        }
        if (direction === 'vertical' || isBoth) {
          styles.height = size;
          styles.flex = `0 0 ${size}px`;
        }
      }

      return styles;
    }, [direction, isBoth, panelStates, maximizedPanel]);

    // ========================================================================
    // RENDU DES PANELS
    // ========================================================================

    const renderPanels = () => {
      const visibleCount = visiblePanels.length;

      return visiblePanels.map((panel, index) => {
        const isLast = index === visibleCount - 1;
        const isCollapsedState = panelStates[panel.id]?.collapsed || false;
        const isMaximizedState = maximizedPanel === panel.id;
        const isActive = currentActivePanel === panel.id;

        const panelStyle = getPanelStyle(panel);

        // Déterminer les positions des poignées
        const handlePositions: ResizableHandlePosition[] = [];
        if (!isLast && !isCollapsedState && !isMaximizedState) {
          if (direction === 'horizontal' || isBoth) {
            handlePositions.push('right');
          }
          if (direction === 'vertical' || isBoth) {
            handlePositions.push('bottom');
          }
          if (isBoth) {
            handlePositions.push('corner');
          }
        }

        // Si le panneau est collapsé, on n'affiche pas les poignées
        const showHandlesForPanel = showHandles && !isCollapsedState && !isMaximizedState && !disabled;

        return (
          <div
            key={panel.id}
            className={cn(
              'relative flex',
              direction === 'horizontal' && 'flex-col',
              direction === 'vertical' && 'flex-row',
              isBoth && 'flex-col',
              panel.className,
              panelClassName,
              isActive && 'ring-1 ring-brand-500/50 ring-inset',
              isMaximizedState && '!flex-1 !w-full !h-full',
              isCollapsedState && 'overflow-hidden'
            )}
            style={panelStyle}
            onClick={() => {
              if (!isControlled) {
                setActivePanel(panel.id);
              }
            }}
            role="group"
            aria-label={`Panneau ${panel.id}`}
          >
            {/* Contenu du panneau */}
            <div
              className={cn(
                'flex-1 overflow-auto',
                isCollapsedState && 'invisible'
              )}
            >
              {panel.content}
            </div>

            {/* Contrôles du panneau */}
            <PanelControls panelId={panel.id} className="absolute top-2 right-2 z-20" />

            {/* Poignées de redimensionnement */}
            {showHandlesForPanel && handlePositions.map((position) => (
              <ResizeHandle
                key={`${panel.id}-${position}`}
                position={position}
                panelId={panel.id}
                className={handleClassName}
                onResizeStart={startResize}
              />
            ))}

            {/* Poignée pour le panneau collapsé */}
            {isCollapsedState && !isMaximizedState && (
              <div className="absolute inset-0 flex items-center justify-center">
                <Button
                  variant="ghost"
                  size="xs"
                  className="h-8 w-8 rounded-full bg-background shadow-md"
                  onClick={() => toggleCollapse(panel.id)}
                >
                  {direction === 'horizontal' ? (
                    <ChevronRightIcon className="h-4 w-4" />
                  ) : (
                    <ChevronDownIcon className="h-4 w-4" />
                  )}
                </Button>
              </div>
            )}
          </div>
        );
      });
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    return (
      <ResizableContext.Provider value={contextValue}>
        <div
          ref={(node) => {
            if (typeof ref === 'function') ref(node);
            else if (ref) ref.current = node;
            containerRef.current = node;
            if (externalContainerRef) {
              (externalContainerRef as React.MutableRefObject<HTMLDivElement>).current = node!;
            }
          }}
          id={resizableId}
          className={cn(
            'flex relative',
            direction === 'horizontal' && 'flex-row',
            direction === 'vertical' && 'flex-col',
            isBoth && 'flex-wrap',
            className
          )}
          style={{
            width: fixedWidth,
            height: fixedHeight,
            gap: gutterSize,
          }}
          aria-label={ariaLabel}
          role="group"
        >
          {renderPanels()}
        </div>
      </ResizableContext.Provider>
    );
  }
);

Resizable.displayName = 'Resizable';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- Resizable.Panel ---
interface ResizablePanelProps {
  id: string;
  children: ReactNode;
  className?: string;
  minSize?: number;
  maxSize?: number;
  defaultSize?: number;
  collapsible?: boolean;
  collapsedSize?: number;
}

export const ResizablePanel: React.FC<ResizablePanelProps> = ({
  id,
  children,
  className,
  minSize,
  maxSize,
  defaultSize,
  collapsible,
  collapsedSize,
}) => {
  const context = useResizableContext();

  // Enregistrer le panneau
  useEffect(() => {
    context?.registerPanel(id);
    return () => context?.unregisterPanel(id);
  }, [id, context]);

  // Définir la taille par défaut
  useEffect(() => {
    if (defaultSize !== undefined && context) {
      context.setPanelSize(id, defaultSize);
    }
  }, [id, defaultSize, context]);

  const isCollapsed = context?.isCollapsed(id) || false;
  const isMaximized = context?.isMaximized(id) || false;
  const size = context?.panelSizes[id] || 0;

  const styles: React.CSSProperties = {};

  if (isCollapsed) {
    const collapsed = collapsedSize || 30;
    styles.width = collapsed;
    styles.height = collapsed;
  }

  if (isMaximized) {
    styles.flex = '1 1 100%';
    styles.width = '100%';
    styles.height = '100%';
  }

  return (
    <div
      className={cn(
        'relative flex-1 overflow-auto',
        isCollapsed && 'min-w-[30px] min-h-[30px] overflow-hidden',
        className
      )}
      style={styles}
    >
      {children}
      {isCollapsed && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Button
            variant="ghost"
            size="xs"
            className="h-6 w-6 rounded-full bg-background shadow-sm"
            onClick={() => context?.toggleCollapse(id)}
          >
            <ChevronRightIcon className="h-3 w-3" />
          </Button>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// HOOKS
// ============================================================================

export const useResizable = (initialPanels: ResizablePanel[]) => {
  const [panels, setPanels] = useState(initialPanels);
  const [sizes, setSizes] = useState<Record<string, number>>({});

  const updatePanelSize = useCallback((panelId: string, size: number) => {
    setSizes((prev) => ({ ...prev, [panelId]: size }));
  }, []);

  const updatePanelVisibility = useCallback((panelId: string, visible: boolean) => {
    setPanels((prev) =>
      prev.map((p) =>
        p.id === panelId ? { ...p, visible } : p
      )
    );
  }, []);

  const resetSizes = useCallback(() => {
    setSizes({});
  }, []);

  return {
    panels,
    sizes,
    setPanels,
    updatePanelSize,
    updatePanelVisibility,
    resetSizes,
  };
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(Resizable, {
  Panel: ResizablePanel,
});

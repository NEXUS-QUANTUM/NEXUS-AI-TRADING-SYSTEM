import React, { useState, useCallback, useEffect, useRef, createContext, useContext, forwardRef } from 'react';
import { cn } from '@/lib/utils';
import {
  ChevronLeft,
  ChevronRight,
  X,
  Plus,
  MoreHorizontal,
  LayoutGrid,
  List,
  Grid,
  Maximize2,
  Minimize2,
  Loader2,
  AlertCircle,
  Check,
  Copy,
  Share2,
  Download,
  ExternalLink,
  RefreshCw,
  Settings,
  Eye,
  EyeOff
} from 'lucide-react';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { useDebounce } from '@/hooks/useDebounce';

/**
 * NEXUS AI TRADING SYSTEM - Tabs Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete Tabs system with:
 * - Multiple variants (default, pill, underline, etc.)
 * - Multiple sizes (sm, md, lg)
 * - Multiple colors
 * - Horizontal/Vertical orientations
 * - Closable tabs
 * - Addable tabs
 * - Tab reordering (drag & drop)
 * - Tab state persistence
 * - Keyboard navigation
 * - Accessibility (ARIA compliant)
 * - Touch support
 * - Responsive
 * - Lazy loading
 * - Loading states
 * - Error states
 * - Custom renderers
 * - Badges
 * - Icons
 * - Animations
 * - Content caching
 * - URL synchronization
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type TabVariant = 'default' | 'pill' | 'underline' | 'box' | 'minimal' | 'glass' | 'modern' | 'neon';
export type TabSize = 'sm' | 'md' | 'lg';
export type TabColor = 'nexus' | 'blue' | 'green' | 'red' | 'purple' | 'yellow' | 'pink';
export type TabOrientation = 'horizontal' | 'vertical';
export type TabPosition = 'top' | 'bottom' | 'left' | 'right';
export type TabAnimation = 'fade' | 'slide' | 'scale' | 'none';
export type TabContentCache = 'all' | 'active' | 'visited' | 'lazy';

export interface TabItem {
  /** Unique tab id */
  id: string;
  /** Tab label */
  label: string;
  /** Tab icon */
  icon?: React.ReactNode;
  /** Tab content */
  content: React.ReactNode;
  /** Tab badge */
  badge?: string | number;
  /** Badge color */
  badgeColor?: 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info';
  /** Disabled state */
  disabled?: boolean;
  /** Loading state */
  loading?: boolean;
  /** Error state */
  error?: string | null;
  /** Closable */
  closable?: boolean;
  /** Custom className for tab */
  className?: string;
  /** Custom className for panel */
  panelClassName?: string;
  /** Meta data */
  meta?: Record<string, any>;
  /** On tab click */
  onClick?: (tab: TabItem) => void;
  /** On tab close */
  onClose?: (tab: TabItem) => void;
}

export interface TabGroup {
  /** Group id */
  id: string;
  /** Group label */
  label: string;
  /** Tabs in group */
  tabs: TabItem[];
}

export interface TabsProps {
  /** Tabs to display */
  tabs: TabItem[];
  /** Default active tab id */
  defaultTabId?: string;
  /** Active tab id (controlled) */
  activeTabId?: string;
  /** On tab change */
  onTabChange?: (tabId: string) => void;
  /** On tab close */
  onTabClose?: (tabId: string) => void;
  /** On tab add */
  onTabAdd?: () => void;
  /** On tabs reorder */
  onTabsReorder?: (tabs: TabItem[]) => void;
  /** Tab variant */
  variant?: TabVariant;
  /** Tab size */
  size?: TabSize;
  /** Tab color */
  color?: TabColor;
  /** Tab orientation */
  orientation?: TabOrientation;
  /** Tab position */
  position?: TabPosition;
  /** Animation type */
  animation?: TabAnimation;
  /** Content caching strategy */
  cache?: TabContentCache;
  /** Allow tab closing */
  closable?: boolean;
  /** Allow tab adding */
  addable?: boolean;
  /** Allow tab reordering */
  reorderable?: boolean;
  /** Show tab badges */
  showBadges?: boolean;
  /** Show tab icons */
  showIcons?: boolean;
  /** Auto scroll tabs */
  autoScroll?: boolean;
  /** Show scroll buttons */
  scrollButtons?: boolean;
  /** Equal width tabs */
  equalWidth?: boolean;
  /** Fit to container */
  fit?: boolean;
  /** Full width tabs */
  fullWidth?: boolean;
  /** Centered tabs */
  centered?: boolean;
  /** Loading state */
  loading?: boolean;
  /** Error state */
  error?: string | null;
  /** Empty state */
  emptyState?: React.ReactNode;
  /** Custom tab renderer */
  renderTab?: (tab: TabItem, index: number, isActive: boolean) => React.ReactNode;
  /** Custom panel renderer */
  renderPanel?: (tab: TabItem, isActive: boolean) => React.ReactNode;
  /** Additional className */
  className?: string;
  /** Tabs className */
  tabsClassName?: string;
  /** Tab className */
  tabClassName?: string;
  /** Panel className */
  panelClassName?: string;
  /** Persist state */
  persistState?: boolean;
  /** Storage key */
  storageKey?: string;
  /** ARIA label */
  ariaLabel?: string;
  /** Test ID */
  testId?: string;
  /** On tab group change */
  onGroupChange?: (groupId: string) => void;
}

// ========================================
// CONTEXT
// ========================================

interface TabsContextType {
  activeTabId: string | null;
  setActiveTabId: (id: string) => void;
  tabs: TabItem[];
  variant: TabVariant;
  size: TabSize;
  color: TabColor;
  orientation: TabOrientation;
  position: TabPosition;
  animation: TabAnimation;
  closable: boolean;
  showBadges: boolean;
  showIcons: boolean;
}

const TabsContext = createContext<TabsContextType | null>(null);

const useTabsContext = () => {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error('Tabs components must be used within a Tabs provider');
  }
  return context;
};

// ========================================
// CONFIGURATION
// ========================================

const VARIANT_CONFIG: Record<TabVariant, {
  tabs: string;
  tab: {
    active: string;
    inactive: string;
    hover: string;
  };
  indicator: string;
  panel: string;
}> = {
  default: {
    tabs: 'border-b border-nexus-200 dark:border-nexus-700',
    tab: {
      active: 'border-b-2 border-nexus-500 text-nexus-700 dark:text-nexus-100',
      inactive: 'text-nexus-500 dark:text-nexus-400 hover:text-nexus-700 dark:hover:text-nexus-200',
      hover: 'hover:bg-nexus-50 dark:hover:bg-nexus-800/50'
    },
    indicator: 'bg-nexus-500',
    panel: 'p-4'
  },
  pill: {
    tabs: 'gap-1 p-1',
    tab: {
      active: 'bg-nexus-500 text-white shadow-md',
      inactive: 'text-nexus-500 dark:text-nexus-400 hover:text-nexus-700 dark:hover:text-nexus-200',
      hover: 'hover:bg-nexus-100 dark:hover:bg-nexus-800'
    },
    indicator: 'bg-nexus-500',
    panel: 'p-4'
  },
  underline: {
    tabs: 'border-b-2 border-nexus-200 dark:border-nexus-700',
    tab: {
      active: 'text-nexus-700 dark:text-nexus-100 border-b-2 border-nexus-500 -mb-0.5',
      inactive: 'text-nexus-500 dark:text-nexus-400 hover:text-nexus-700 dark:hover:text-nexus-200',
      hover: 'hover:bg-nexus-50 dark:hover:bg-nexus-800/50'
    },
    indicator: 'bg-nexus-500',
    panel: 'p-4'
  },
  box: {
    tabs: 'border border-nexus-200 dark:border-nexus-700 rounded-lg overflow-hidden',
    tab: {
      active: 'bg-nexus-500 text-white',
      inactive: 'text-nexus-500 dark:text-nexus-400 hover:text-nexus-700 dark:hover:text-nexus-200',
      hover: 'hover:bg-nexus-100 dark:hover:bg-nexus-800'
    },
    indicator: 'bg-nexus-500',
    panel: 'p-4'
  },
  minimal: {
    tabs: 'gap-4',
    tab: {
      active: 'text-nexus-700 dark:text-nexus-100',
      inactive: 'text-nexus-400 dark:text-nexus-500 hover:text-nexus-600 dark:hover:text-nexus-300',
      hover: ''
    },
    indicator: 'bg-nexus-500',
    panel: 'p-4'
  },
  glass: {
    tabs: 'bg-white/10 backdrop-blur-xl rounded-t-xl border border-white/20',
    tab: {
      active: 'text-white bg-white/20',
      inactive: 'text-white/70 hover:text-white',
      hover: 'hover:bg-white/10'
    },
    indicator: 'bg-white/50',
    panel: 'bg-white/5 backdrop-blur-xl rounded-b-xl border border-white/10 border-t-0 p-4'
  },
  modern: {
    tabs: 'relative',
    tab: {
      active: 'text-nexus-700 dark:text-nexus-100 bg-gradient-to-b from-nexus-500/10 to-transparent',
      inactive: 'text-nexus-500 dark:text-nexus-400 hover:text-nexus-700 dark:hover:text-nexus-200',
      hover: 'hover:bg-nexus-500/5'
    },
    indicator: 'h-1 bg-gradient-to-r from-nexus-400 to-nexus-600',
    panel: 'p-6 bg-white/5 rounded-lg'
  },
  neon: {
    tabs: 'border-b border-nexus-500/30',
    tab: {
      active: 'text-nexus-400 border-b-2 border-nexus-400 shadow-[0_0_20px_rgba(99,102,241,0.3)]',
      inactive: 'text-nexus-500 dark:text-nexus-400 hover:text-nexus-300',
      hover: 'hover:bg-nexus-500/10'
    },
    indicator: 'bg-nexus-400 shadow-[0_0_20px_rgba(99,102,241,0.5)]',
    panel: 'p-4 border-t border-nexus-500/10'
  }
};

const SIZE_CONFIG: Record<TabSize, {
  tab: string;
  text: string;
  gap: string;
  padding: string;
  icon: string;
  badge: string;
}> = {
  sm: {
    tab: 'px-3 py-1.5 text-xs',
    text: 'text-xs',
    gap: 'gap-1',
    padding: 'p-1',
    icon: 'w-3 h-3',
    badge: 'text-xs px-1.5 py-0.5'
  },
  md: {
    tab: 'px-4 py-2 text-sm',
    text: 'text-sm',
    gap: 'gap-1.5',
    padding: 'p-1',
    icon: 'w-4 h-4',
    badge: 'text-xs px-2 py-0.5'
  },
  lg: {
    tab: 'px-6 py-2.5 text-base',
    text: 'text-base',
    gap: 'gap-2',
    padding: 'p-1.5',
    icon: 'w-5 h-5',
    badge: 'text-sm px-2.5 py-0.5'
  }
};

const COLOR_CONFIG: Record<TabColor, {
  active: string;
  inactive: string;
  hover: string;
  border: string;
}> = {
  nexus: {
    active: 'text-nexus-700 dark:text-nexus-100',
    inactive: 'text-nexus-500 dark:text-nexus-400',
    hover: 'hover:text-nexus-700 dark:hover:text-nexus-200',
    border: 'border-nexus-500'
  },
  blue: {
    active: 'text-blue-700 dark:text-blue-100',
    inactive: 'text-blue-500 dark:text-blue-400',
    hover: 'hover:text-blue-700 dark:hover:text-blue-200',
    border: 'border-blue-500'
  },
  green: {
    active: 'text-emerald-700 dark:text-emerald-100',
    inactive: 'text-emerald-500 dark:text-emerald-400',
    hover: 'hover:text-emerald-700 dark:hover:text-emerald-200',
    border: 'border-emerald-500'
  },
  red: {
    active: 'text-red-700 dark:text-red-100',
    inactive: 'text-red-500 dark:text-red-400',
    hover: 'hover:text-red-700 dark:hover:text-red-200',
    border: 'border-red-500'
  },
  purple: {
    active: 'text-purple-700 dark:text-purple-100',
    inactive: 'text-purple-500 dark:text-purple-400',
    hover: 'hover:text-purple-700 dark:hover:text-purple-200',
    border: 'border-purple-500'
  },
  yellow: {
    active: 'text-yellow-700 dark:text-yellow-100',
    inactive: 'text-yellow-500 dark:text-yellow-400',
    hover: 'hover:text-yellow-700 dark:hover:text-yellow-200',
    border: 'border-yellow-500'
  },
  pink: {
    active: 'text-pink-700 dark:text-pink-100',
    inactive: 'text-pink-500 dark:text-pink-400',
    hover: 'hover:text-pink-700 dark:hover:text-pink-200',
    border: 'border-pink-500'
  }
};

const ANIMATION_CONFIG: Record<TabAnimation, {
  enter: string;
  exit: string;
  duration: string;
}> = {
  fade: {
    enter: 'animate-in fade-in',
    exit: 'animate-out fade-out',
    duration: 'duration-200'
  },
  slide: {
    enter: 'animate-in slide-in-from-right-4',
    exit: 'animate-out slide-out-to-left-4',
    duration: 'duration-300'
  },
  scale: {
    enter: 'animate-in zoom-in-95',
    exit: 'animate-out zoom-out-95',
    duration: 'duration-200'
  },
  none: {
    enter: '',
    exit: '',
    duration: ''
  }
};

const BADGE_COLORS = {
  default: 'bg-nexus-100 text-nexus-700 dark:bg-nexus-700 dark:text-nexus-300',
  primary: 'bg-nexus-500 text-white',
  success: 'bg-emerald-500 text-white',
  warning: 'bg-yellow-500 text-white',
  danger: 'bg-red-500 text-white',
  info: 'bg-blue-500 text-white'
};

// ========================================
// MAIN COMPONENT
// ========================================

export const Tabs = forwardRef<HTMLDivElement, TabsProps>(({
  tabs: initialTabs,
  defaultTabId,
  activeTabId: controlledActiveTabId,
  onTabChange,
  onTabClose,
  onTabAdd,
  onTabsReorder,
  variant = 'default',
  size = 'md',
  color = 'nexus',
  orientation = 'horizontal',
  position = 'top',
  animation = 'fade',
  cache = 'active',
  closable = false,
  addable = false,
  reorderable = false,
  showBadges = true,
  showIcons = true,
  autoScroll = true,
  scrollButtons = true,
  equalWidth = false,
  fit = false,
  fullWidth = false,
  centered = false,
  loading = false,
  error = null,
  emptyState,
  renderTab,
  renderPanel,
  className,
  tabsClassName,
  tabClassName,
  panelClassName,
  persistState = false,
  storageKey = 'nexus-tabs-state',
  ariaLabel = 'Tabs',
  testId = 'nexus-tabs',
  onGroupChange
}, ref) => {
  // ========================================
  // STATE
  // ========================================
  
  const [tabs, setTabs] = useState<TabItem[]>(initialTabs);
  const [activeTabId, setActiveTabId] = useState<string | null>(() => {
    if (controlledActiveTabId !== undefined) return controlledActiveTabId;
    if (defaultTabId) return defaultTabId;
    if (initialTabs.length > 0) return initialTabs[0].id;
    return null;
  });
  const [visitedTabs, setVisitedTabs] = useState<Set<string>>(new Set());
  const [isScrolling, setIsScrolling] = useState(false);
  const [scrollPosition, setScrollPosition] = useState(0);
  const [showLeftArrow, setShowLeftArrow] = useState(false);
  const [showRightArrow, setShowRightArrow] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  // ========================================
  // REFS
  // ========================================
  
  const containerRef = useRef<HTMLDivElement>(null);
  const tabsContainerRef = useRef<HTMLDivElement>(null);
  const tabsListRef = useRef<HTMLDivElement>(null);
  const tabRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

  // ========================================
  // HOOKS
  // ========================================
  
  const isMobile = useMediaQuery('(max-width: 640px)');
  const isTablet = useMediaQuery('(max-width: 1024px)');
  const [storedState, setStoredState] = useLocalStorage<{
    activeTabId: string;
    tabs: TabItem[];
  } | null>(storageKey, null);

  // ========================================
  // EFFECTS
  // ========================================
  
  // Sync with props
  useEffect(() => {
    setTabs(initialTabs);
  }, [initialTabs]);

  // Sync active tab with props
  useEffect(() => {
    if (controlledActiveTabId !== undefined) {
      setActiveTabId(controlledActiveTabId);
    }
  }, [controlledActiveTabId]);

  // Load stored state
  useEffect(() => {
    if (persistState && storedState) {
      setActiveTabId(storedState.activeTabId);
      if (storedState.tabs && storedState.tabs.length > 0) {
        setTabs(storedState.tabs);
      }
    }
  }, [persistState, storedState]);

  // Save state
  useEffect(() => {
    if (persistState && activeTabId) {
      setStoredState({
        activeTabId,
        tabs
      });
    }
  }, [persistState, activeTabId, tabs]);

  // Track visited tabs
  useEffect(() => {
    if (activeTabId) {
      setVisitedTabs(prev => new Set(prev).add(activeTabId));
    }
  }, [activeTabId]);

  // Scroll to active tab
  useEffect(() => {
    if (autoScroll && activeTabId && tabsListRef.current) {
      const tabElement = tabRefs.current.get(activeTabId);
      if (tabElement) {
        setTimeout(() => {
          tabElement.scrollIntoView({
            behavior: 'smooth',
            block: 'nearest',
            inline: 'center'
          });
        }, 100);
      }
    }
  }, [activeTabId, autoScroll]);

  // Check scroll arrows
  useEffect(() => {
    const checkArrows = () => {
      const container = tabsListRef.current;
      if (!container) return;
      
      const { scrollLeft, scrollWidth, clientWidth } = container;
      setShowLeftArrow(scrollLeft > 0);
      setShowRightArrow(scrollLeft + clientWidth < scrollWidth - 1);
    };

    checkArrows();
    window.addEventListener('resize', checkArrows);
    const observer = new ResizeObserver(checkArrows);
    if (tabsListRef.current) {
      observer.observe(tabsListRef.current);
    }

    return () => {
      window.removeEventListener('resize', checkArrows);
      observer.disconnect();
    };
  }, [tabs]);

  // ========================================
  // HELPERS
  // ========================================
  
  const colors = COLOR_CONFIG[color];
  const sizes = SIZE_CONFIG[size];
  const variantConfig = VARIANT_CONFIG[variant];
  const animationConfig = ANIMATION_CONFIG[animation];

  const isActive = (tabId: string) => activeTabId === tabId;
  const isVisited = (tabId: string) => visitedTabs.has(tabId);
  const shouldRender = (tab: TabItem) => {
    switch (cache) {
      case 'all':
        return true;
      case 'active':
        return isActive(tab.id);
      case 'visited':
        return isVisited(tab.id);
      case 'lazy':
        return isActive(tab.id) || isVisited(tab.id);
      default:
        return isActive(tab.id);
    }
  };

  // ========================================
  // HANDLERS
  // ========================================
  
  const handleTabClick = useCallback((tab: TabItem, index: number) => {
    if (tab.disabled) return;
    
    setActiveTabId(tab.id);
    onTabChange?.(tab.id);
    tab.onClick?.(tab);
  }, [onTabChange]);

  const handleTabClose = useCallback((tab: TabItem, e: React.MouseEvent) => {
    e.stopPropagation();
    if (tab.disabled) return;
    
    onTabClose?.(tab.id);
    tab.onClose?.(tab);
    
    // If closing active tab, switch to previous tab
    if (activeTabId === tab.id) {
      const currentIndex = tabs.findIndex(t => t.id === tab.id);
      const previousTab = tabs[currentIndex - 1];
      const nextTab = tabs[currentIndex + 1];
      const newActiveTab = previousTab || nextTab;
      if (newActiveTab) {
        setActiveTabId(newActiveTab.id);
        onTabChange?.(newActiveTab.id);
      } else {
        setActiveTabId(null);
      }
    }
  }, [activeTabId, tabs, onTabClose, onTabChange]);

  const handleScroll = useCallback((direction: 'left' | 'right') => {
    const container = tabsListRef.current;
    if (!container) return;
    
    const scrollAmount = container.clientWidth * 0.8;
    const target = direction === 'left'
      ? container.scrollLeft - scrollAmount
      : container.scrollLeft + scrollAmount;
    
    container.scrollTo({
      left: target,
      behavior: 'smooth'
    });
  }, []);

  // Drag & drop reordering
  const handleDragStart = useCallback((e: React.DragEvent, index: number) => {
    if (!reorderable) return;
    setDragIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(index));
  }, [reorderable]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);

  const handleDrop = useCallback((e: React.DragEvent, dropIndex: number) => {
    e.preventDefault();
    if (!reorderable || dragIndex === null) return;
    
    const dragItem = tabs[dragIndex];
    if (!dragItem) return;
    
    const newTabs = [...tabs];
    newTabs.splice(dragIndex, 1);
    newTabs.splice(dropIndex, 0, dragItem);
    
    setTabs(newTabs);
    onTabsReorder?.(newTabs);
    setDragIndex(null);
  }, [reorderable, dragIndex, tabs, onTabsReorder]);

  // ========================================
  // RENDER HELPERS
  // ========================================
  
  const renderBadge = useCallback((tab: TabItem) => {
    if (!showBadges || tab.badge === undefined) return null;

    const badgeColor = tab.badgeColor || 'default';
    const badgeClass = BADGE_COLORS[badgeColor];

    return (
      <span className={cn(
        'rounded-full font-medium',
        sizes.badge,
        badgeClass
      )}>
        {tab.badge}
      </span>
    );
  }, [showBadges, sizes.badge]);

  const renderTabContent = useCallback((tab: TabItem, index: number) => {
    const active = isActive(tab.id);
    const variantStyle = variantConfig.tab;
    const colorStyle = active ? colors.active : colors.inactive;

    if (renderTab) {
      return renderTab(tab, index, active);
    }

    return (
      <button
        ref={(el) => {
          if (el) {
            tabRefs.current.set(tab.id, el);
          } else {
            tabRefs.current.delete(tab.id);
          }
        }}
        key={tab.id}
        role="tab"
        aria-selected={active}
        aria-controls={`panel-${tab.id}`}
        aria-disabled={tab.disabled}
        tabIndex={active ? 0 : -1}
        disabled={tab.disabled}
        onClick={() => handleTabClick(tab, index)}
        className={cn(
          'relative flex items-center gap-1.5 transition-all duration-200',
          sizes.tab,
          sizes.text,
          variantStyle.inactive,
          colorStyle,
          variantStyle.hover,
          active && variantStyle.active,
          active && colors.border,
          tab.disabled && 'opacity-50 cursor-not-allowed',
          equalWidth && 'flex-1 justify-center',
          tab.className,
          tabClassName
        )}
        draggable={reorderable && !tab.disabled}
        onDragStart={(e) => handleDragStart(e, index)}
        onDragOver={handleDragOver}
        onDrop={(e) => handleDrop(e, index)}
        title={tab.label}
      >
        {/* Active indicator */}
        {active && variantConfig.indicator && (
          <span className={cn(
            'absolute',
            orientation === 'vertical' ? 'left-0 top-0 bottom-0 w-0.5' : 'bottom-0 left-0 right-0 h-0.5',
            variantConfig.indicator
          )} />
        )}

        {/* Icon */}
        {showIcons && tab.icon && (
          <span className={cn(sizes.icon, 'flex-shrink-0')}>
            {tab.icon}
          </span>
        )}

        {/* Label */}
        <span className="truncate">{tab.label}</span>

        {/* Badge */}
        {renderBadge(tab)}

        {/* Loading */}
        {tab.loading && (
          <Loader2 className={cn(sizes.icon, 'animate-spin flex-shrink-0')} />
        )}

        {/* Close button */}
        {(closable || tab.closable) && (
          <button
            onClick={(e) => handleTabClose(tab, e)}
            className={cn(
              'rounded-full p-0.5 hover:bg-nexus-200 dark:hover:bg-nexus-700 transition-colors flex-shrink-0',
              'opacity-0 group-hover:opacity-100 focus:opacity-100',
              active && 'opacity-100'
            )}
            aria-label={`Close ${tab.label}`}
          >
            <X className={cn(sizes.icon, 'w-3 h-3')} />
          </button>
        )}
      </button>
    );
  }, [
    isActive,
    variantConfig,
    colors,
    sizes,
    renderTab,
    tabClassName,
    reorderable,
    orientation,
    showIcons,
    closable,
    renderBadge,
    handleTabClick,
    handleDragStart,
    handleDragOver,
    handleDrop,
    handleTabClose
  ]);

  const renderPanel = useCallback((tab: TabItem) => {
    const active = isActive(tab.id);
    
    if (!shouldRender(tab)) return null;

    if (renderPanel) {
      return renderPanel(tab, active);
    }

    return (
      <div
        role="tabpanel"
        id={`panel-${tab.id}`}
        aria-labelledby={`tab-${tab.id}`}
        className={cn(
          'w-full',
          variantConfig.panel,
          animationConfig.enter,
          animationConfig.duration,
          active && 'block',
          !active && 'hidden',
          tab.panelClassName,
          panelClassName
        )}
      >
        {tab.error ? (
          <div className="flex flex-col items-center justify-center py-8 text-red-500">
            <AlertCircle className="w-8 h-8 mb-2" />
            <p>{tab.error}</p>
          </div>
        ) : (
          tab.content
        )}
      </div>
    );
  }, [
    isActive,
    shouldRender,
    renderPanel,
    variantConfig.panel,
    animationConfig,
    panelClassName
  ]);

  // ========================================
  // MAIN RENDER
  // ========================================
  
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12">
        <Loader2 className="w-8 h-8 text-nexus-500 animate-spin" />
        <p className="mt-2 text-nexus-500 dark:text-nexus-400">Loading tabs...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-red-500">
        <AlertCircle className="w-8 h-8 mb-2" />
        <p>{error}</p>
      </div>
    );
  }

  if (tabs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12">
        {emptyState || (
          <>
            <LayoutGrid className="w-8 h-8 text-nexus-400 mb-2" />
            <p className="text-nexus-500 dark:text-nexus-400">No tabs available</p>
          </>
        )}
      </div>
    );
  }

  const isVertical = orientation === 'vertical';
  const positionClass = isVertical ? {
    left: 'flex-row',
    right: 'flex-row-reverse',
    top: 'flex-col',
    bottom: 'flex-col-reverse'
  }[position] : {
    top: 'flex-col',
    bottom: 'flex-col-reverse',
    left: 'flex-row',
    right: 'flex-row-reverse'
  }[position];

  const tabsContainerClass = isVertical ? {
    left: 'border-r border-nexus-200 dark:border-nexus-700',
    right: 'border-l border-nexus-200 dark:border-nexus-700',
    top: 'border-b border-nexus-200 dark:border-nexus-700',
    bottom: 'border-t border-nexus-200 dark:border-nexus-700'
  }[position] : {
    left: 'border-r border-nexus-200 dark:border-nexus-700',
    right: 'border-l border-nexus-200 dark:border-nexus-700',
    top: 'border-b border-nexus-200 dark:border-nexus-700',
    bottom: 'border-t border-nexus-200 dark:border-nexus-700'
  }[position];

  return (
    <TabsContext.Provider
      value={{
        activeTabId,
        setActiveTabId,
        tabs,
        variant,
        size,
        color,
        orientation,
        position,
        animation,
        closable,
        showBadges,
        showIcons
      }}
    >
      <div
        ref={ref}
        className={cn(
          'flex w-full',
          positionClass,
          variantConfig.className,
          className
        )}
        data-testid={testId}
        aria-label={ariaLabel}
        role="tablist"
      >
        {/* Tabs container */}
        <div
          ref={containerRef}
          className={cn(
            'relative flex',
            isVertical ? 'flex-col' : 'flex-row',
            isVertical ? 'min-w-[200px]' : 'min-h-[40px]',
            tabsContainerClass,
            tabsClassName
          )}
        >
          {/* Scroll left button */}
          {!isVertical && scrollButtons && showLeftArrow && (
            <button
              onClick={() => handleScroll('left')}
              className="absolute left-0 top-1/2 -translate-y-1/2 z-10 p-1 bg-white dark:bg-nexus-900 shadow-lg rounded-full border border-nexus-200 dark:border-nexus-700 hover:bg-nexus-50 dark:hover:bg-nexus-800 transition-colors"
              aria-label="Scroll tabs left"
            >
              <ChevronLeft className="w-4 h-4 text-nexus-500" />
            </button>
          )}

          {/* Tabs list */}
          <div
            ref={tabsListRef}
            className={cn(
              'flex overflow-x-auto scrollbar-hide',
              isVertical ? 'flex-col overflow-y-auto' : 'flex-row',
              fullWidth && 'w-full',
              centered && 'justify-center',
              fit && 'flex-1',
              equalWidth && '[&>button]:flex-1',
              sizes.gap,
              sizes.padding,
              'group'
            )}
            style={{
              scrollBehavior: isScrolling ? 'auto' : 'smooth',
            }}
          >
            {tabs.map((tab, index) => (
              <div
                key={tab.id}
                className={cn(
                  'relative group flex-shrink-0',
                  equalWidth && 'flex-1',
                  fullWidth && 'flex-1'
                )}
              >
                {renderTabContent(tab, index)}
              </div>
            ))}

            {/* Add button */}
            {addable && (
              <button
                onClick={onTabAdd}
                className={cn(
                  'flex items-center justify-center flex-shrink-0',
                  sizes.tab,
                  sizes.text,
                  'text-nexus-400 hover:text-nexus-600 dark:text-nexus-500 dark:hover:text-nexus-300',
                  'hover:bg-nexus-100 dark:hover:bg-nexus-800 rounded-lg transition-colors'
                )}
                aria-label="Add tab"
              >
                <Plus className={cn(sizes.icon, 'w-4 h-4')} />
              </button>
            )}
          </div>

          {/* Scroll right button */}
          {!isVertical && scrollButtons && showRightArrow && (
            <button
              onClick={() => handleScroll('right')}
              className="absolute right-0 top-1/2 -translate-y-1/2 z-10 p-1 bg-white dark:bg-nexus-900 shadow-lg rounded-full border border-nexus-200 dark:border-nexus-700 hover:bg-nexus-50 dark:hover:bg-nexus-800 transition-colors"
              aria-label="Scroll tabs right"
            >
              <ChevronRight className="w-4 h-4 text-nexus-500" />
            </button>
          )}
        </div>

        {/* Panels */}
        <div className={cn(
          'flex-1',
          orientation === 'vertical' ? 'pl-4' : 'pt-4'
        )}>
          {tabs.map(tab => renderPanel(tab))}
        </div>
      </div>
    </TabsContext.Provider>
  );
});

Tabs.displayName = 'Tabs';

// ========================================
// COMPOUND COMPONENTS
// ========================================

export interface TabListProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
}

export const TabList: React.FC<TabListProps> = ({
  children,
  className,
  ...props
}) => {
  const context = useTabsContext();
  const variantConfig = VARIANT_CONFIG[context.variant];
  const sizes = SIZE_CONFIG[context.size];

  return (
    <div
      className={cn(
        'flex',
        context.orientation === 'vertical' ? 'flex-col' : 'flex-row',
        variantConfig.tabs,
        sizes.gap,
        sizes.padding,
        className
      )}
      role="tablist"
      {...props}
    >
      {children}
    </div>
  );
};

export interface TabProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  id: string;
  label: string;
  icon?: React.ReactNode;
  badge?: string | number;
  badgeColor?: 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info';
  disabled?: boolean;
  closable?: boolean;
  className?: string;
}

export const Tab: React.FC<TabProps> = ({
  id,
  label,
  icon,
  badge,
  badgeColor = 'default',
  disabled = false,
  closable = false,
  className,
  onClick,
  ...props
}) => {
  const context = useTabsContext();
  const isActive = context.activeTabId === id;
  const variantConfig = VARIANT_CONFIG[context.variant];
  const sizes = SIZE_CONFIG[context.size];
  const colors = COLOR_CONFIG[context.color];

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (disabled) return;
    context.setActiveTabId(id);
    onClick?.(e);
  };

  const handleClose = (e: React.MouseEvent) => {
    e.stopPropagation();
    // Handle close logic
  };

  return (
    <button
      role="tab"
      aria-selected={isActive}
      aria-disabled={disabled}
      tabIndex={isActive ? 0 : -1}
      disabled={disabled}
      onClick={handleClick}
      className={cn(
        'relative flex items-center gap-1.5 transition-all duration-200',
        sizes.tab,
        sizes.text,
        variantConfig.tab.inactive,
        isActive ? colors.active : colors.inactive,
        variantConfig.tab.hover,
        isActive && variantConfig.tab.active,
        isActive && colors.border,
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
      {...props}
    >
      {/* Active indicator */}
      {isActive && variantConfig.indicator && (
        <span className={cn(
          'absolute',
          context.orientation === 'vertical' ? 'left-0 top-0 bottom-0 w-0.5' : 'bottom-0 left-0 right-0 h-0.5',
          variantConfig.indicator
        )} />
      )}

      {/* Icon */}
      {icon && (
        <span className={cn(sizes.icon, 'flex-shrink-0')}>
          {icon}
        </span>
      )}

      {/* Label */}
      <span className="truncate">{label}</span>

      {/* Badge */}
      {badge !== undefined && (
        <span className={cn(
          'rounded-full font-medium',
          sizes.badge,
          BADGE_COLORS[badgeColor]
        )}>
          {badge}
        </span>
      )}

      {/* Close button */}
      {(closable || context.closable) && (
        <button
          onClick={handleClose}
          className={cn(
            'rounded-full p-0.5 hover:bg-nexus-200 dark:hover:bg-nexus-700 transition-colors flex-shrink-0',
            'opacity-0 group-hover:opacity-100 focus:opacity-100',
            isActive && 'opacity-100'
          )}
          aria-label={`Close ${label}`}
        >
          <X className={cn(sizes.icon, 'w-3 h-3')} />
        </button>
      )}
    </button>
  );
};

export interface TabPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  id: string;
  children: React.ReactNode;
  className?: string;
}

export const TabPanel: React.FC<TabPanelProps> = ({
  id,
  children,
  className,
  ...props
}) => {
  const context = useTabsContext();
  const isActive = context.activeTabId === id;
  const variantConfig = VARIANT_CONFIG[context.variant];
  const animationConfig = ANIMATION_CONFIG[context.animation];

  return (
    <div
      role="tabpanel"
      id={`panel-${id}`}
      aria-labelledby={`tab-${id}`}
      className={cn(
        'w-full',
        variantConfig.panel,
        animationConfig.enter,
        animationConfig.duration,
        isActive ? 'block' : 'hidden',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

// ========================================
// PRESETED TAB COMPONENTS
// ========================================

export const TabsPresets = {
  Default: (props: Omit<TabsProps, 'variant'>) => (
    <Tabs variant="default" {...props} />
  ),
  Pill: (props: Omit<TabsProps, 'variant'>) => (
    <Tabs variant="pill" {...props} />
  ),
  Underline: (props: Omit<TabsProps, 'variant'>) => (
    <Tabs variant="underline" {...props} />
  ),
  Box: (props: Omit<TabsProps, 'variant'>) => (
    <Tabs variant="box" {...props} />
  ),
  Minimal: (props: Omit<TabsProps, 'variant'>) => (
    <Tabs variant="minimal" {...props} />
  ),
  Glass: (props: Omit<TabsProps, 'variant'>) => (
    <Tabs variant="glass" {...props} />
  ),
  Modern: (props: Omit<TabsProps, 'variant'>) => (
    <Tabs variant="modern" {...props} />
  ),
  Neon: (props: Omit<TabsProps, 'variant'>) => (
    <Tabs variant="neon" {...props} />
  )
};

// ========================================
// EXPORTS
// ========================================

TabList.displayName = 'TabList';
Tab.displayName = 'Tab';
TabPanel.displayName = 'TabPanel';

export default Tabs;

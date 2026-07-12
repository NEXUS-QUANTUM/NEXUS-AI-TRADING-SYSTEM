// apps/web/src/components/common/NavigationMenu.tsx
'use client';

import React, {
  Fragment,
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
  Children,
  isValidElement,
  cloneElement,
} from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  Menu,
  Transition,
  Popover,
  PopoverButton,
  PopoverPanel,
  Listbox,
  Combobox,
  Dialog,
} from '@headlessui/react';
import {
  ChevronDownIcon,
  ChevronRightIcon,
  ChevronLeftIcon,
  Bars3Icon,
  XMarkIcon,
  HomeIcon,
  ChartBarIcon,
  ChartPieIcon,
  Cog6ToothIcon,
  UserCircleIcon,
  ArrowRightOnRectangleIcon,
  SunIcon,
  MoonIcon,
  ComputerDesktopIcon,
  MagnifyingGlassIcon,
  BellIcon,
  QuestionMarkCircleIcon,
  LifebuoyIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  InformationCircleIcon,
  PlusCircleIcon,
  MinusCircleIcon,
  FolderIcon,
  FolderOpenIcon,
  SparklesIcon,
  RocketLaunchIcon,
  ShieldCheckIcon,
  CurrencyDollarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ClockIcon,
  CalendarIcon,
  UserGroupIcon,
  BuildingOfficeIcon,
  GlobeAltIcon,
  DevicePhoneMobileIcon,
  CommandLineIcon,
  CodeBracketIcon,
  BookOpenIcon,
  AcademicCapIcon,
  GiftIcon,
  HeartIcon,
  StarIcon,
  TrophyIcon,
  FireIcon,
  BoltIcon,
  CloudIcon,
  ServerIcon,
  DatabaseIcon,
  WifiIcon,
  SignalIcon,
  AdjustmentsHorizontalIcon,
  Squares2X2Icon,
  ListBulletIcon,
  ViewColumnsIcon,
  SquaresPlusIcon,
  QueueListIcon,
  TableCellsIcon,
  RectangleStackIcon,
  CpuChipIcon,
  CircleStackIcon,
  BeakerIcon,
  MicrophoneIcon,
  VideoCameraIcon,
  PhotoIcon,
  MusicalNoteIcon,
  PaintBrushIcon,
  PencilIcon,
  TrashIcon,
  DocumentDuplicateIcon,
  PaperClipIcon,
  LinkIcon,
  EnvelopeIcon,
  ChatBubbleLeftRightIcon,
  PhoneIcon,
  MapPinIcon,
  FlagIcon,
  TagIcon,
  TicketIcon,
  CreditCardIcon,
  WalletIcon,
  BanknotesIcon,
  ShoppingCartIcon,
  TruckIcon,
  PackageIcon,
  CubeIcon,
  CubeTransparentIcon,
  CakeIcon,
  PizzaIcon,
  CoffeeIcon,
  BeakerIcon as BeakerIcon2,
  Square2StackIcon,
  RectangleGroupIcon,
} from '@heroicons/react/24/outline';
import {
  ChevronDownIcon as ChevronDownSolid,
  ChevronRightIcon as ChevronRightSolid,
  HomeIcon as HomeSolid,
  ChartBarIcon as ChartBarSolid,
  ChartPieIcon as ChartPieSolid,
  Cog6ToothIcon as CogSolid,
  UserCircleIcon as UserSolid,
  BellIcon as BellSolid,
  SparklesIcon as SparklesSolid,
  RocketLaunchIcon as RocketSolid,
  ShieldCheckIcon as ShieldSolid,
  CurrencyDollarIcon as CurrencySolid,
  ArrowTrendingUpIcon as TrendingUpSolid,
  ArrowTrendingDownIcon as TrendingDownSolid,
} from '@heroicons/react/24/solid';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import { useTheme } from 'next-themes';
import { useAuth } from '@/hooks/useAuth';
import { useSubscription } from '@/hooks/useSubscription';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/common/Avatar';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';
import { Skeleton } from '@/components/common/Skeleton';
import { ScrollArea } from '@/components/common/ScrollArea';
import { Separator } from '@/components/common/Separator';
import { Input } from '@/components/common/Input';
import { Command, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem } from '@/components/common/Command';

// ============================================================================
// TYPES
// ============================================================================

export type NavigationItemType = 'link' | 'dropdown' | 'submenu' | 'divider' | 'header' | 'search' | 'user' | 'notification' | 'theme';

export type NavigationVariant = 'horizontal' | 'vertical' | 'mobile' | 'sidebar' | 'breadcrumb';

export type NavigationSize = 'sm' | 'md' | 'lg' | 'xl';

export type NavigationTheme = 'light' | 'dark' | 'system' | 'brand';

export type NavigationPosition = 'top' | 'bottom' | 'left' | 'right';

export interface NavigationItem {
  /** Identifiant unique */
  id: string;
  /** Libellé affiché */
  label: string;
  /** Type d'élément */
  type: NavigationItemType;
  /** URL de destination (pour type 'link') */
  href?: string;
  /** Icône (Heroicons) */
  icon?: ReactNode;
  /** Icône active (Heroicons) */
  activeIcon?: ReactNode;
  /** Sous-éléments (pour type 'dropdown' ou 'submenu') */
  items?: NavigationItem[];
  /** Badge à afficher */
  badge?: string | number;
  /** Couleur du badge */
  badgeColor?: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'brand';
  /** Si l'élément est actif */
  isActive?: boolean;
  /** Si l'élément est désactivé */
  isDisabled?: boolean;
  /** Si l'élément est en chargement */
  isLoading?: boolean;
  /** Raccourci clavier */
  shortcut?: string;
  /** Description au survol */
  description?: string;
  /** Permissions requises */
  requiredPermissions?: string[];
  /** Rôles requis */
  requiredRoles?: string[];
  /** État de la notification (pour type 'notification') */
  notification?: {
    count: number;
    unread: boolean;
    type?: 'info' | 'success' | 'warning' | 'danger';
  };
  /** Avatar (pour type 'user') */
  avatar?: {
    src?: string;
    alt?: string;
    fallback: string;
  };
  /** Callback onClick */
  onClick?: (e: React.MouseEvent) => void;
  /** Props supplémentaires */
  [key: string]: any;
}

export interface NavigationGroup {
  id: string;
  label?: string;
  icon?: ReactNode;
  items: NavigationItem[];
  collapsible?: boolean;
  defaultCollapsed?: boolean;
}

export interface NavigationMenuProps {
  /** Éléments de navigation */
  items?: NavigationItem[];
  /** Groupes de navigation */
  groups?: NavigationGroup[];
  /** Variante d'affichage */
  variant?: NavigationVariant;
  /** Taille des éléments */
  size?: NavigationSize;
  /** Thème */
  theme?: NavigationTheme;
  /** Position */
  position?: NavigationPosition;
  /** Logo/Brand */
  brand?: {
    logo?: ReactNode;
    title?: string;
    subtitle?: string;
    href?: string;
    className?: string;
  };
  /** Classes supplémentaires */
  className?: string;
  /** Classes pour le conteneur */
  containerClassName?: string;
  /** Classes pour les éléments */
  itemClassName?: string;
  /** Classes pour les sous-menus */
  submenuClassName?: string;
  /** Classe pour l'élément actif */
  activeClassName?: string;
  /** Si la navigation est mobile */
  isMobile?: boolean;
  /** Contrôle l'ouverture du menu mobile */
  isMobileOpen?: boolean;
  /** Callback pour le toggle mobile */
  onMobileToggle?: (isOpen: boolean) => void;
  /** Profondeur maximale des sous-menus */
  maxDepth?: number;
  /** Si les éléments sont collapsibles */
  collapsible?: boolean;
  /** Afficher les icônes */
  showIcons?: boolean;
  /** Afficher les libellés */
  showLabels?: boolean;
  /** Afficher les raccourcis */
  showShortcuts?: boolean;
  /** Afficher les badges */
  showBadges?: boolean;
  /** Afficher les descriptions */
  showDescriptions?: boolean;
  /** Afficher les notifications */
  showNotifications?: boolean;
  /** Afficher les avatars */
  showAvatars?: boolean;
  /** Afficher la recherche */
  showSearch?: boolean;
  /** Afficher le sélecteur de thème */
  showThemeToggle?: boolean;
  /** Afficher les notifications */
  showNotificationBell?: boolean;
  /** Afficher le profil utilisateur */
  showUserMenu?: boolean;
  /** Afficher le breadcrumb */
  showBreadcrumb?: boolean;
  /** Afficher les séparateurs */
  showDividers?: boolean;
  /** Afficher les headers de groupe */
  showGroupHeaders?: boolean;
  /** Animation du sous-menu */
  animation?: 'fade' | 'slide' | 'scale' | 'none';
  /** Durée de l'animation (ms) */
  animationDuration?: number;
  /** Raccourci pour la recherche */
  searchShortcut?: string;
  /** Placeholder de la recherche */
  searchPlaceholder?: string;
  /** Callback de recherche */
  onSearch?: (query: string) => void;
  /** Résultats de recherche */
  searchResults?: NavigationItem[];
  /** Callback de changement de thème */
  onThemeChange?: (theme: string) => void;
  /** Callback de notification */
  onNotificationClick?: (item: NavigationItem) => void;
  /** Callback de profil */
  onUserAction?: (action: string, item: NavigationItem) => void;
  /** Callback de logout */
  onLogout?: () => void;
  /** Callback de changement de page */
  onNavigate?: (item: NavigationItem) => void;
  /** État de chargement */
  isLoading?: boolean;
  /** État d'erreur */
  error?: string | null;
  /** Éléments supplémentaires dans le footer */
  footerContent?: ReactNode;
  /** Éléments supplémentaires dans le header */
  headerContent?: ReactNode;
  /** Accessibilité */
  ariaLabel?: string;
  /** ID */
  id?: string;
}

// ============================================================================
// CONTEXT
// ============================================================================

interface NavigationContextType {
  variant: NavigationVariant;
  size: NavigationSize;
  theme: NavigationTheme;
  isMobile: boolean;
  isMobileOpen: boolean;
  setMobileOpen: (open: boolean) => void;
  activePath: string;
  activeItem: string | null;
  setActiveItem: (id: string | null) => void;
  expandedItems: string[];
  toggleExpanded: (id: string) => void;
  maxDepth: number;
  showIcons: boolean;
  showLabels: boolean;
  showShortcuts: boolean;
  showBadges: boolean;
  showDescriptions: boolean;
  showAvatars: boolean;
  onNavigate?: (item: NavigationItem) => void;
  navigate: (item: NavigationItem) => void;
  depth: number;
}

const NavigationContext = createContext<NavigationContextType | null>(null);

const useNavigationContext = () => {
  const context = useContext(NavigationContext);
  if (!context) {
    throw new Error('Navigation components must be used within NavigationMenu');
  }
  return context;
};

// ============================================================================
// COMPOSANTS INTERNES
// ============================================================================

// --- Breadcrumb ---
interface BreadcrumbProps {
  items: NavigationItem[];
  className?: string;
}

const Breadcrumb: React.FC<BreadcrumbProps> = ({ items, className }) => {
  const pathname = usePathname();

  const breadcrumbs = useMemo(() => {
    const pathSegments = pathname.split('/').filter(Boolean);
    const crumbs: NavigationItem[] = [];

    // Home
    crumbs.push({
      id: 'home',
      label: 'Accueil',
      href: '/',
      icon: <HomeIcon className="h-4 w-4" />,
    });

    // Build crumbs from segments
    let currentPath = '';
    for (const segment of pathSegments) {
      currentPath += `/${segment}`;
      const label = segment
        .split('-')
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
      crumbs.push({
        id: segment,
        label,
        href: currentPath,
      });
    }

    return crumbs;
  }, [pathname]);

  if (items.length > 0) {
    return (
      <nav className={cn('flex items-center gap-1 text-sm', className)}>
        {items.map((item, index) => (
          <Fragment key={item.id}>
            {index > 0 && (
              <ChevronRightIcon className="h-3 w-3 text-gray-400 flex-shrink-0" />
            )}
            {index === items.length - 1 ? (
              <span className="text-gray-900 dark:text-white font-medium truncate max-w-[200px]">
                {item.label}
              </span>
            ) : (
              <Link
                href={item.href || '#'}
                className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
              >
                {item.label}
              </Link>
            )}
          </Fragment>
        ))}
      </nav>
    );
  }

  return (
    <nav className={cn('flex items-center gap-1 text-sm', className)} aria-label="Breadcrumb">
      {breadcrumbs.map((item, index) => (
        <Fragment key={item.id}>
          {index > 0 && (
            <ChevronRightIcon className="h-3 w-3 text-gray-400 flex-shrink-0" />
          )}
          {index === breadcrumbs.length - 1 ? (
            <span className="text-gray-900 dark:text-white font-medium truncate max-w-[200px]">
              {item.label}
            </span>
          ) : (
            <Link
              href={item.href || '#'}
              className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
            >
              {item.icon && <span className="mr-1">{item.icon}</span>}
              {item.label}
            </Link>
          )}
        </Fragment>
      ))}
    </nav>
  );
};

// --- NavigationItemRenderer ---
interface NavigationItemRendererProps {
  item: NavigationItem;
  depth?: number;
  className?: string;
}

const NavigationItemRenderer: React.FC<NavigationItemRendererProps> = ({
  item,
  depth = 0,
  className,
}) => {
  const context = useNavigationContext();
  const {
    variant,
    size,
    isMobile,
    showIcons,
    showLabels,
    showShortcuts,
    showBadges,
    showDescriptions,
    showAvatars,
    activeItem,
    setActiveItem,
    expandedItems,
    toggleExpanded,
    maxDepth,
    onNavigate,
    navigate,
  } = context;

  const isActive = item.isActive || (item.href && item.href === context.activePath);
  const isExpanded = expandedItems.includes(item.id);
  const hasChildren = item.items && item.items.length > 0;
  const isDisabled = item.isDisabled || item.isLoading;
  const isDivider = item.type === 'divider';
  const isHeader = item.type === 'header';
  const isSubmenu = item.type === 'submenu' || hasChildren;

  // --- Rendu des types spéciaux ---
  if (isDivider) {
    return <Separator className={cn('my-2', className)} />;
  }

  if (isHeader) {
    return (
      <div className={cn('px-3 py-2 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider', className)}>
        {item.label}
      </div>
    );
  }

  if (item.type === 'search') {
    return <NavigationSearch item={item} depth={depth} />;
  }

  if (item.type === 'user') {
    return <NavigationUser item={item} depth={depth} />;
  }

  if (item.type === 'notification') {
    return <NavigationNotification item={item} depth={depth} />;
  }

  if (item.type === 'theme') {
    return <NavigationThemeToggle depth={depth} />;
  }

  // --- Sous-menu ---
  if (isSubmenu && depth < maxDepth) {
    return (
      <Popover className="relative">
        {({ open, close }) => (
          <>
            <PopoverButton
              as="div"
              className={cn(
                'group flex w-full cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm transition-all',
                isActive
                  ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-400'
                  : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800',
                isDisabled && 'opacity-50 cursor-not-allowed',
                size === 'sm' && 'px-2 py-1.5 text-xs',
                size === 'lg' && 'px-4 py-2.5 text-base',
                size === 'xl' && 'px-5 py-3 text-lg',
                className
              )}
              onClick={() => {
                if (isDisabled) return;
                if (variant === 'vertical' || isMobile) {
                  toggleExpanded(item.id);
                }
              }}
              onMouseEnter={() => {
                if (variant === 'horizontal' && !isMobile) {
                  setActiveItem(item.id);
                }
              }}
              onMouseLeave={() => {
                if (variant === 'horizontal' && !isMobile) {
                  setTimeout(() => setActiveItem(null), 100);
                }
              }}
              disabled={isDisabled}
            >
              {showIcons && item.icon && (
                <span className={cn(
                  'flex-shrink-0',
                  isActive ? 'text-brand-500' : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'
                )}>
                  {isActive && item.activeIcon ? item.activeIcon : item.icon}
                </span>
              )}

              {showLabels && <span className="flex-1 text-left">{item.label}</span>}

              {showBadges && item.badge && (
                <Badge variant={item.badgeColor || 'primary'} size="sm">
                  {item.badge}
                </Badge>
              )}

              {showShortcuts && item.shortcut && (
                <kbd className="hidden lg:inline-block text-xs text-gray-400 dark:text-gray-500">
                  {item.shortcut}
                </kbd>
              )}

              {!isMobile && (
                <ChevronDownIcon
                  className={cn(
                    'h-4 w-4 transition-transform',
                    open && 'rotate-180'
                  )}
                />
              )}
              {isMobile && (
                <ChevronRightIcon
                  className={cn(
                    'h-4 w-4 transition-transform',
                    isExpanded && 'rotate-90'
                  )}
                />
              )}
            </PopoverButton>

            {/* Sous-menu panel */}
            {variant === 'horizontal' && !isMobile && (
              <PopoverPanel
                as={Fragment}
                transition
                className="absolute left-0 top-full z-50 mt-1 w-64 rounded-xl bg-white shadow-xl ring-1 ring-black/5 dark:bg-gray-900 dark:ring-gray-700/50"
              >
                {({ close: closePopover }) => (
                  <NavigationSubMenu
                    items={item.items || []}
                    depth={depth + 1}
                    onItemClick={(subItem) => {
                      closePopover();
                      if (subItem.href) {
                        navigate(subItem);
                      }
                      if (subItem.onClick) {
                        subItem.onClick({} as React.MouseEvent);
                      }
                    }}
                  />
                )}
              </PopoverPanel>
            )}

            {/* Sous-menu mobile / vertical */}
            {(variant === 'vertical' || isMobile) && isExpanded && (
              <div className="ml-4 border-l border-gray-200 dark:border-gray-700 pl-4">
                <NavigationSubMenu
                  items={item.items || []}
                  depth={depth + 1}
                  onItemClick={(subItem) => {
                    if (subItem.href) {
                      navigate(subItem);
                    }
                    if (subItem.onClick) {
                      subItem.onClick({} as React.MouseEvent);
                    }
                    if (isMobile) {
                      // Fermer le menu mobile
                    }
                  }}
                />
              </div>
            )}
          </>
        )}
      </Popover>
    );
  }

  // --- Lien simple ---
  const linkContent = (
    <span className="flex flex-1 items-center gap-2">
      {showIcons && item.icon && (
        <span className={cn(
          'flex-shrink-0',
          isActive ? 'text-brand-500' : 'text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'
        )}>
          {isActive && item.activeIcon ? item.activeIcon : item.icon}
        </span>
      )}
      {showLabels && <span>{item.label}</span>}
      {showBadges && item.badge && (
        <Badge variant={item.badgeColor || 'primary'} size="sm">
          {item.badge}
        </Badge>
      )}
      {showShortcuts && item.shortcut && (
        <kbd className="hidden lg:inline-block text-xs text-gray-400 dark:text-gray-500 ml-auto">
          {item.shortcut}
        </kbd>
      )}
    </span>
  );

  // --- Rendu du lien ---
  if (item.href) {
    return (
      <Link
        href={item.href}
        className={cn(
          'group flex items-center rounded-lg px-3 py-2 text-sm transition-all',
          isActive
            ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-400'
            : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800',
          isDisabled && 'opacity-50 pointer-events-none',
          size === 'sm' && 'px-2 py-1.5 text-xs',
          size === 'lg' && 'px-4 py-2.5 text-base',
          size === 'xl' && 'px-5 py-3 text-lg',
          className
        )}
        onClick={() => {
          if (isDisabled) return;
          if (item.onClick) {
            item.onClick({} as React.MouseEvent);
          }
          navigate(item);
        }}
        aria-current={isActive ? 'page' : undefined}
      >
        {linkContent}
        {showDescriptions && item.description && (
          <span className="hidden text-xs text-gray-400 dark:text-gray-500 truncate max-w-[100px]">
            {item.description}
          </span>
        )}
      </Link>
    );
  }

  // --- Bouton simple ---
  return (
    <button
      className={cn(
        'group flex w-full items-center rounded-lg px-3 py-2 text-sm transition-all',
        isActive
          ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-400'
          : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800',
        isDisabled && 'opacity-50 cursor-not-allowed',
        size === 'sm' && 'px-2 py-1.5 text-xs',
        size === 'lg' && 'px-4 py-2.5 text-base',
        size === 'xl' && 'px-5 py-3 text-lg',
        className
      )}
      onClick={() => {
        if (isDisabled) return;
        if (item.onClick) {
          item.onClick({} as React.MouseEvent);
        }
        navigate(item);
      }}
      disabled={isDisabled}
    >
      {linkContent}
    </button>
  );
};

// --- NavigationSubMenu ---
interface NavigationSubMenuProps {
  items: NavigationItem[];
  depth: number;
  onItemClick?: (item: NavigationItem) => void;
  className?: string;
}

const NavigationSubMenu: React.FC<NavigationSubMenuProps> = ({
  items,
  depth,
  onItemClick,
  className,
}) => {
  return (
    <div className={cn('flex flex-col gap-0.5 py-1', className)}>
      {items.map((item) => (
        <NavigationItemRenderer
          key={item.id}
          item={item}
          depth={depth}
          className="!rounded-lg"
        />
      ))}
    </div>
  );
};

// --- NavigationSearch ---
interface NavigationSearchProps {
  item: NavigationItem;
  depth: number;
}

const NavigationSearch: React.FC<NavigationSearchProps> = ({ item, depth }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<NavigationItem[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Raccourci clavier pour la recherche
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSearch = useCallback((value: string) => {
    setQuery(value);
    if (item.onSearch) {
      const searchResults = item.onSearch(value);
      setResults(Array.isArray(searchResults) ? searchResults : []);
    }
  }, [item.onSearch]);

  return (
    <div className="relative px-3 py-2">
      <div className="relative">
        <MagnifyingGlassIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          ref={inputRef}
          type="text"
          className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 py-2 pl-9 pr-4 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:focus:ring-brand-500/20"
          placeholder={item.label || 'Rechercher...'}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            handleSearch(e.target.value);
            setIsOpen(e.target.value.length > 0);
          }}
          onFocus={() => {
            if (query.length > 0) setIsOpen(true);
          }}
          onBlur={() => {
            setTimeout(() => setIsOpen(false), 200);
          }}
        />
        <kbd className="absolute right-3 top-1/2 -translate-y-1/2 hidden lg:inline-flex items-center gap-0.5 rounded bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 text-xs text-gray-500 dark:text-gray-400 font-mono">
          <span className="text-[10px]">⌘</span>K
        </kbd>
      </div>

      <AnimatePresence>
        {isOpen && results.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="absolute left-3 right-3 top-full mt-2 z-50 max-h-[300px] overflow-y-auto rounded-xl bg-white shadow-xl ring-1 ring-black/5 dark:bg-gray-900 dark:ring-gray-700/50"
          >
            {results.map((result) => (
              <button
                key={result.id}
                className="flex w-full items-center gap-2 px-4 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                onClick={() => {
                  if (result.href) {
                    // navigation
                  }
                  setIsOpen(false);
                  setQuery('');
                }}
              >
                {result.icon && <span className="text-gray-400">{result.icon}</span>}
                <span>{result.label}</span>
                {result.badge && (
                  <Badge variant={result.badgeColor || 'primary'} size="sm" className="ml-auto">
                    {result.badge}
                  </Badge>
                )}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {isOpen && results.length === 0 && query.length > 0 && (
        <div className="absolute left-3 right-3 top-full mt-2 z-50 rounded-xl bg-white p-4 text-center text-sm text-gray-500 shadow-xl ring-1 ring-black/5 dark:bg-gray-900 dark:text-gray-400 dark:ring-gray-700/50">
          Aucun résultat trouvé
        </div>
      )}
    </div>
  );
};

// --- NavigationUser ---
interface NavigationUserProps {
  item: NavigationItem;
  depth: number;
}

const NavigationUser: React.FC<NavigationUserProps> = ({ item, depth }) => {
  const { onLogout, onUserAction } = useNavigationContext();
  const { user } = useAuth();

  const userItems: NavigationItem[] = [
    {
      id: 'profile',
      label: 'Mon profil',
      href: '/dashboard/profile',
      icon: <UserCircleIcon className="h-4 w-4" />,
    },
    {
      id: 'settings',
      label: 'Paramètres',
      href: '/dashboard/settings',
      icon: <Cog6ToothIcon className="h-4 w-4" />,
    },
    {
      id: 'subscription',
      label: 'Abonnement',
      href: '/dashboard/subscription',
      icon: <CurrencyDollarIcon className="h-4 w-4" />,
    },
    {
      id: 'divider-1',
      type: 'divider',
      label: '',
    },
    {
      id: 'help',
      label: 'Aide',
      href: '/help',
      icon: <LifebuoyIcon className="h-4 w-4" />,
    },
    {
      id: 'feedback',
      label: 'Retour',
      href: '/feedback',
      icon: <ChatBubbleLeftRightIcon className="h-4 w-4" />,
    },
    {
      id: 'divider-2',
      type: 'divider',
      label: '',
    },
    {
      id: 'logout',
      label: 'Déconnexion',
      icon: <ArrowRightOnRectangleIcon className="h-4 w-4" />,
      onClick: () => {
        if (onLogout) onLogout();
        if (onUserAction) onUserAction('logout', item);
      },
    },
  ];

  return (
    <Menu as="div" className="relative">
      <Menu.Button className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-all hover:bg-gray-100 dark:hover:bg-gray-800">
        <Avatar size="sm" className="h-8 w-8">
          <AvatarImage src={item.avatar?.src || user?.avatar} alt={item.avatar?.alt || user?.name || 'User'} />
          <AvatarFallback>
            {item.avatar?.fallback || user?.name?.charAt(0) || 'U'}
          </AvatarFallback>
        </Avatar>
        <span className="hidden lg:inline text-gray-700 dark:text-gray-300">
          {item.label || user?.name || 'Utilisateur'}
        </span>
        <ChevronDownIcon className="hidden lg:block h-4 w-4 text-gray-400" />
      </Menu.Button>

      <Transition
        as={Fragment}
        enter="transition duration-100 ease-out"
        enterFrom="transform scale-95 opacity-0"
        enterTo="transform scale-100 opacity-100"
        leave="transition duration-75 ease-in"
        leaveFrom="transform scale-100 opacity-100"
        leaveTo="transform scale-95 opacity-0"
      >
        <Menu.Items className="absolute right-0 top-full mt-2 w-56 origin-top-right rounded-xl bg-white shadow-xl ring-1 ring-black/5 dark:bg-gray-900 dark:ring-gray-700/50 z-50">
          <div className="p-2">
            {userItems.map((userItem) => {
              if (userItem.type === 'divider') {
                return <Separator key={userItem.id} className="my-2" />;
              }
              return (
                <Menu.Item key={userItem.id}>
                  {({ active }) => (
                    <button
                      className={cn(
                        'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
                        active
                          ? 'bg-gray-100 dark:bg-gray-800'
                          : '',
                        userItem.id === 'logout' && 'text-red-600 dark:text-red-400'
                      )}
                      onClick={() => {
                        if (userItem.onClick) {
                          userItem.onClick({} as React.MouseEvent);
                        }
                        if (userItem.href) {
                          // navigate
                        }
                      }}
                    >
                      {userItem.icon}
                      {userItem.label}
                    </button>
                  )}
                </Menu.Item>
              );
            })}
          </div>
        </Menu.Items>
      </Transition>
    </Menu>
  );
};

// --- NavigationNotification ---
interface NavigationNotificationProps {
  item: NavigationItem;
  depth: number;
}

const NavigationNotification: React.FC<NavigationNotificationProps> = ({ item, depth }) => {
  const [notifications, setNotifications] = useState<NavigationItem[]>(item.items || []);
  const [unreadCount, setUnreadCount] = useState(item.notification?.count || 0);

  const handleMarkAsRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) =>
        n.id === id
          ? { ...n, notification: { ...n.notification!, unread: false } }
          : n
      )
    );
    setUnreadCount((prev) => Math.max(0, prev - 1));
  }, []);

  const handleMarkAllAsRead = useCallback(() => {
    setNotifications((prev) =>
      prev.map((n) => ({
        ...n,
        notification: n.notification ? { ...n.notification, unread: false } : undefined,
      }))
    );
    setUnreadCount(0);
  }, []);

  return (
    <Popover className="relative">
      <Popover.Button className="relative flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-all hover:bg-gray-100 dark:hover:bg-gray-800">
        <BellIcon className="h-5 w-5 text-gray-400" />
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-bold text-white">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
        <span className="hidden lg:inline text-gray-700 dark:text-gray-300">
          {item.label}
        </span>
        <ChevronDownIcon className="hidden lg:block h-4 w-4 text-gray-400" />
      </Popover.Button>

      <Transition
        as={Fragment}
        enter="transition duration-100 ease-out"
        enterFrom="transform scale-95 opacity-0"
        enterTo="transform scale-100 opacity-100"
        leave="transition duration-75 ease-in"
        leaveFrom="transform scale-100 opacity-100"
        leaveTo="transform scale-95 opacity-0"
      >
        <Popover.Panel className="absolute right-0 top-full mt-2 w-80 origin-top-right rounded-xl bg-white shadow-xl ring-1 ring-black/5 dark:bg-gray-900 dark:ring-gray-700/50 z-50">
          <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-700 p-4">
            <span className="font-semibold text-gray-900 dark:text-white">
              Notifications
            </span>
            {unreadCount > 0 && (
              <button
                className="text-sm text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
                onClick={handleMarkAllAsRead}
              >
                Tout marquer comme lu
              </button>
            )}
          </div>

          <ScrollArea className="max-h-[300px]">
            <div className="p-2">
              {notifications.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-8 text-center text-gray-500 dark:text-gray-400">
                  <CheckCircleIcon className="h-12 w-12 text-gray-300 dark:text-gray-600" />
                  <p>Aucune notification</p>
                </div>
              ) : (
                notifications.map((notif) => (
                  <button
                    key={notif.id}
                    className={cn(
                      'flex w-full items-start gap-3 rounded-lg p-3 transition-colors',
                      notif.notification?.unread
                        ? 'bg-brand-50 dark:bg-brand-900/20'
                        : 'hover:bg-gray-50 dark:hover:bg-gray-800'
                    )}
                    onClick={() => {
                      handleMarkAsRead(notif.id);
                      if (notif.onClick) {
                        notif.onClick({} as React.MouseEvent);
                      }
                      if (notif.href) {
                        // navigate
                      }
                    }}
                  >
                    <div className="flex-shrink-0 mt-0.5">
                      {notif.icon || (
                        <div className={cn(
                          'h-8 w-8 rounded-full flex items-center justify-center',
                          notif.notification?.type === 'success' && 'bg-green-100 dark:bg-green-900/30',
                          notif.notification?.type === 'warning' && 'bg-yellow-100 dark:bg-yellow-900/30',
                          notif.notification?.type === 'danger' && 'bg-red-100 dark:bg-red-900/30',
                          (!notif.notification?.type || notif.notification?.type === 'info') && 'bg-blue-100 dark:bg-blue-900/30',
                        )}>
                          {notif.notification?.type === 'success' && <CheckCircleIcon className="h-4 w-4 text-green-600" />}
                          {notif.notification?.type === 'warning' && <ExclamationTriangleIcon className="h-4 w-4 text-yellow-600" />}
                          {notif.notification?.type === 'danger' && <ExclamationTriangleIcon className="h-4 w-4 text-red-600" />}
                          {(!notif.notification?.type || notif.notification?.type === 'info') && <InformationCircleIcon className="h-4 w-4 text-blue-600" />}
                        </div>
                      )}
                    </div>
                    <div className="flex-1 text-left">
                      <p className="text-sm font-medium text-gray-900 dark:text-white">
                        {notif.label}
                      </p>
                      {notif.description && (
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {notif.description}
                        </p>
                      )}
                      {notif.notification?.unread && (
                        <span className="inline-block mt-1 h-1.5 w-1.5 rounded-full bg-brand-500" />
                      )}
                    </div>
                  </button>
                ))
              )}
            </div>
          </ScrollArea>
        </Popover.Panel>
      </Transition>
    </Popover>
  );
};

// --- NavigationThemeToggle ---
interface NavigationThemeToggleProps {
  depth: number;
}

const NavigationThemeToggle: React.FC<NavigationThemeToggleProps> = ({ depth }) => {
  const { resolvedTheme, setTheme } = useTheme();
  const [isOpen, setIsOpen] = useState(false);

  const themes = [
    { id: 'light', label: 'Clair', icon: <SunIcon className="h-4 w-4" /> },
    { id: 'dark', label: 'Sombre', icon: <MoonIcon className="h-4 w-4" /> },
    { id: 'system', label: 'Système', icon: <ComputerDesktopIcon className="h-4 w-4" /> },
  ];

  const currentTheme = themes.find((t) => t.id === resolvedTheme) || themes[0];

  return (
    <Menu as="div" className="relative">
      <Menu.Button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-all hover:bg-gray-100 dark:hover:bg-gray-800">
        {currentTheme.icon}
        <span className="flex-1 text-left text-gray-700 dark:text-gray-300">
          Thème
        </span>
        <span className="text-xs text-gray-400">{currentTheme.label}</span>
        <ChevronDownIcon className="h-4 w-4 text-gray-400" />
      </Menu.Button>

      <Transition
        as={Fragment}
        enter="transition duration-100 ease-out"
        enterFrom="transform scale-95 opacity-0"
        enterTo="transform scale-100 opacity-100"
        leave="transition duration-75 ease-in"
        leaveFrom="transform scale-100 opacity-100"
        leaveTo="transform scale-95 opacity-0"
      >
        <Menu.Items className="absolute left-0 top-full mt-1 w-full origin-top-left rounded-xl bg-white shadow-xl ring-1 ring-black/5 dark:bg-gray-900 dark:ring-gray-700/50 z-50">
          <div className="p-1">
            {themes.map((theme) => (
              <Menu.Item key={theme.id}>
                {({ active }) => (
                  <button
                    className={cn(
                      'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
                      active && 'bg-gray-100 dark:bg-gray-800',
                      resolvedTheme === theme.id && 'bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-400'
                    )}
                    onClick={() => setTheme(theme.id)}
                  >
                    {theme.icon}
                    {theme.label}
                    {resolvedTheme === theme.id && (
                      <CheckCircleIcon className="ml-auto h-4 w-4 text-brand-500" />
                    )}
                  </button>
                )}
              </Menu.Item>
            ))}
          </div>
        </Menu.Items>
      </Transition>
    </Menu>
  );
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const NavigationMenu = forwardRef<HTMLElement, NavigationMenuProps>(
  (props, ref) => {
    const {
      items = [],
      groups = [],
      variant = 'horizontal',
      size = 'md',
      theme = 'system',
      position = 'top',
      brand,
      className,
      containerClassName,
      itemClassName,
      submenuClassName,
      activeClassName,
      isMobile = false,
      isMobileOpen: externalMobileOpen = false,
      onMobileToggle,
      maxDepth = 3,
      collapsible = true,
      showIcons = true,
      showLabels = true,
      showShortcuts = false,
      showBadges = true,
      showDescriptions = false,
      showAvatars = true,
      showSearch = false,
      showThemeToggle = false,
      showNotificationBell = false,
      showUserMenu = false,
      showBreadcrumb = false,
      showDividers = true,
      showGroupHeaders = true,
      animation = 'fade',
      animationDuration = 150,
      searchPlaceholder = 'Rechercher...',
      onSearch,
      searchResults = [],
      onThemeChange,
      onNotificationClick,
      onUserAction,
      onLogout,
      onNavigate,
      isLoading = false,
      error = null,
      footerContent,
      headerContent,
      ariaLabel = 'Navigation principale',
      id,
      ...rest
    } = props;

    const pathname = usePathname();
    const router = useRouter();
    const { resolvedTheme: currentTheme } = useTheme();
    const [activeItem, setActiveItem] = useState<string | null>(null);
    const [expandedItems, setExpandedItems] = useState<string[]>([]);
    const [isMobileOpen, setIsMobileOpen] = useState(externalMobileOpen);
    const [searchQuery, setSearchQuery] = useState('');

    // ========================================================================
    // HELPERS
    // ========================================================================

    const toggleExpanded = useCallback((id: string) => {
      setExpandedItems((prev) =>
        prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
      );
    }, []);

    const navigate = useCallback((item: NavigationItem) => {
      if (item.href) {
        router.push(item.href);
      }
      if (onNavigate) {
        onNavigate(item);
      }
      if (isMobile && onMobileToggle) {
        onMobileToggle(false);
        setIsMobileOpen(false);
      }
    }, [router, onNavigate, isMobile, onMobileToggle]);

    // ========================================================================
    // EFFETS
    // ========================================================================

    // Sync mobile open state
    useEffect(() => {
      setIsMobileOpen(externalMobileOpen);
    }, [externalMobileOpen]);

    // Find active item from path
    useEffect(() => {
      const findActive = (navItems: NavigationItem[]): string | null => {
        for (const item of navItems) {
          if (item.href && pathname === item.href) {
            return item.id;
          }
          if (item.href && pathname.startsWith(item.href) && item.href !== '/') {
            return item.id;
          }
          if (item.items) {
            const found = findActive(item.items);
            if (found) return found;
          }
        }
        return null;
      };

      const allItems = [...items, ...groups.flatMap((g) => g.items)];
      const active = findActive(allItems);
      setActiveItem(active);
    }, [pathname, items, groups]);

    // ========================================================================
    // CONTEXT
    // ========================================================================

    const contextValue = useMemo<NavigationContextType>(
      () => ({
        variant,
        size,
        theme: currentTheme as NavigationTheme,
        isMobile,
        isMobileOpen,
        setMobileOpen: (open: boolean) => {
          setIsMobileOpen(open);
          if (onMobileToggle) onMobileToggle(open);
        },
        activePath: pathname,
        activeItem,
        setActiveItem,
        expandedItems,
        toggleExpanded,
        maxDepth,
        showIcons,
        showLabels,
        showShortcuts,
        showBadges,
        showDescriptions,
        showAvatars,
        onNavigate,
        navigate,
        depth: 0,
      }),
      [
        variant,
        size,
        currentTheme,
        isMobile,
        isMobileOpen,
        pathname,
        activeItem,
        expandedItems,
        maxDepth,
        showIcons,
        showLabels,
        showShortcuts,
        showBadges,
        showDescriptions,
        showAvatars,
        onNavigate,
        navigate,
        onMobileToggle,
      ]
    );

    // ========================================================================
    // RENDU
    // ========================================================================

    if (isLoading) {
      return <NavigationSkeleton variant={variant} size={size} />;
    }

    if (error) {
      return <NavigationError error={error} />;
    }

    // Construction des éléments de navigation
    const navItems = items.length > 0 ? items : groups.flatMap((g) => g.items);

    // Rendu du brand
    const renderBrand = () => {
      if (!brand) return null;

      return (
        <Link
          href={brand.href || '/'}
          className={cn(
            'flex items-center gap-2 font-semibold text-gray-900 dark:text-white',
            brand.className
          )}
        >
          {brand.logo}
          <div className="flex flex-col">
            {brand.title && <span className="text-lg">{brand.title}</span>}
            {brand.subtitle && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {brand.subtitle}
              </span>
            )}
          </div>
        </Link>
      );
    };

    // Rendu du menu
    const renderMenu = () => {
      return (
        <nav
          ref={ref}
          id={id}
          className={cn(
            'flex',
            variant === 'horizontal' && 'flex-row items-center gap-1',
            variant === 'vertical' && 'flex-col gap-0.5',
            variant === 'mobile' && 'flex-col gap-0.5 p-4',
            variant === 'sidebar' && 'flex-col gap-0.5 p-4',
            variant === 'breadcrumb' && 'flex-row items-center',
            className
          )}
          aria-label={ariaLabel}
          {...rest}
        >
          {variant !== 'breadcrumb' && renderBrand()}

          {variant === 'breadcrumb' ? (
            <Breadcrumb items={items} className={className} />
          ) : (
            <>
              {navItems.map((item) => (
                <NavigationItemRenderer
                  key={item.id}
                  item={item}
                  depth={0}
                  className={itemClassName}
                />
              ))}
            </>
          )}
        </nav>
      );
    };

    // Rendu du header (recherche + actions)
    const renderHeader = () => {
      return (
        <div className="flex items-center gap-2">
          {showSearch && (
            <div className="relative">
              <input
                type="text"
                className="w-48 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 py-1.5 pl-8 pr-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:focus:ring-brand-500/20"
                placeholder={searchPlaceholder}
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  if (onSearch) onSearch(e.target.value);
                }}
              />
              <MagnifyingGlassIcon className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <kbd className="absolute right-2 top-1/2 -translate-y-1/2 hidden lg:inline-flex items-center gap-0.5 rounded bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 text-xs text-gray-500 dark:text-gray-400 font-mono">
                <span className="text-[10px]">⌘</span>K
              </kbd>
            </div>
          )}

          {showThemeToggle && <NavigationThemeToggle depth={0} />}

          {showNotificationBell && (
            <NavigationNotification
              item={{
                id: 'notifications',
                label: 'Notifications',
                type: 'notification',
                notification: { count: 3, unread: true },
                items: [
                  {
                    id: 'notif-1',
                    label: 'Nouveau signal de trading',
                    description: 'Un signal bullish a été détecté sur BTC/USD',
                    notification: { unread: true, type: 'success' },
                  },
                  {
                    id: 'notif-2',
                    label: 'Mise à jour du système',
                    description: 'La version 3.2.0 est disponible',
                    notification: { unread: true, type: 'info' },
                  },
                ],
              }}
              depth={0}
            />
          )}

          {showUserMenu && (
            <NavigationUser
              item={{
                id: 'user',
                label: 'Profil',
                type: 'user',
                avatar: {
                  fallback: 'U',
                },
              }}
              depth={0}
            />
          )}
        </div>
      );
    };

    // Rendu du menu mobile
    const renderMobileMenu = () => {
      if (!isMobile) return null;

      return (
        <Transition show={isMobileOpen} as={Fragment}>
          <Dialog
            as="div"
            className="relative z-50 lg:hidden"
            onClose={() => {
              setIsMobileOpen(false);
              if (onMobileToggle) onMobileToggle(false);
            }}
          >
            <Transition.Child
              as={Fragment}
              enter="transition-opacity duration-300"
              enterFrom="opacity-0"
              enterTo="opacity-100"
              leave="transition-opacity duration-300"
              leaveFrom="opacity-100"
              leaveTo="opacity-0"
            >
              <div className="fixed inset-0 bg-black/50" />
            </Transition.Child>

            <Transition.Child
              as={Fragment}
              enter="transition-transform duration-300 ease-out"
              enterFrom="-translate-x-full"
              enterTo="translate-x-0"
              leave="transition-transform duration-300 ease-in"
              leaveFrom="translate-x-0"
              leaveTo="-translate-x-full"
            >
              <Dialog.Panel className="fixed left-0 top-0 h-full w-80 bg-white dark:bg-gray-900 shadow-xl">
                <div className="flex h-full flex-col">
                  <div className="flex items-center justify-between border-b border-gray-200 dark:border-gray-700 p-4">
                    {renderBrand()}
                    <button
                      className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                      onClick={() => {
                        setIsMobileOpen(false);
                        if (onMobileToggle) onMobileToggle(false);
                      }}
                    >
                      <XMarkIcon className="h-5 w-5" />
                    </button>
                  </div>

                  <div className="flex-1 overflow-y-auto p-2">
                    <NavigationContext.Provider value={contextValue}>
                      {renderMenu()}
                    </NavigationContext.Provider>
                  </div>

                  {footerContent && (
                    <div className="border-t border-gray-200 dark:border-gray-700 p-4">
                      {footerContent}
                    </div>
                  )}
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </Dialog>
        </Transition>
      );
    };

    return (
      <NavigationContext.Provider value={contextValue}>
        <div className={cn('relative', containerClassName)}>
          {/* Barre de navigation principale */}
          <div
            className={cn(
              'flex items-center justify-between',
              variant === 'horizontal' && 'px-4 py-2',
              variant === 'vertical' && 'flex-col items-stretch',
              variant === 'sidebar' && 'flex-col items-stretch h-full',
              variant === 'breadcrumb' && 'py-2 px-4',
              variant === 'mobile' && 'hidden lg:flex',
            )}
          >
            {variant !== 'mobile' ? (
              <>
                <div className="flex items-center gap-2">
                  {isMobile && (
                    <button
                      className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 lg:hidden"
                      onClick={() => {
                        setIsMobileOpen(true);
                        if (onMobileToggle) onMobileToggle(true);
                      }}
                    >
                      <Bars3Icon className="h-5 w-5" />
                    </button>
                  )}
                  {!isMobile && renderBrand()}
                </div>

                {variant === 'horizontal' && !isMobile && (
                  <div className="hidden lg:flex flex-1 items-center justify-center">
                    {renderMenu()}
                  </div>
                )}

                {variant === 'vertical' && (
                  <div className="flex-1">{renderMenu()}</div>
                )}

                {variant === 'sidebar' && (
                  <div className="flex-1">
                    {headerContent}
                    {renderMenu()}
                    {footerContent}
                  </div>
                )}

                <div className="flex items-center gap-2">
                  {renderHeader()}
                </div>
              </>
            ) : (
              renderMenu()
            )}
          </div>

          {/* Menu mobile */}
          {isMobile && renderMobileMenu()}

          {/* Version mobile de la barre de navigation */}
          {isMobile && !isMobileOpen && (
            <div className="lg:hidden flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-2">
                <button
                  className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                  onClick={() => {
                    setIsMobileOpen(true);
                    if (onMobileToggle) onMobileToggle(true);
                  }}
                >
                  <Bars3Icon className="h-5 w-5" />
                </button>
                {renderBrand()}
              </div>
              <div className="flex items-center gap-2">
                {showSearch && (
                  <button className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800">
                    <MagnifyingGlassIcon className="h-5 w-5" />
                  </button>
                )}
                {showNotificationBell && (
                  <button className="relative rounded-lg p-2 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800">
                    <BellIcon className="h-5 w-5" />
                    <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                      3
                    </span>
                  </button>
                )}
                {showUserMenu && (
                  <button className="rounded-lg p-1">
                    <Avatar size="sm" className="h-8 w-8">
                      <AvatarFallback>U</AvatarFallback>
                    </Avatar>
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </NavigationContext.Provider>
    );
  }
);

NavigationMenu.displayName = 'NavigationMenu';

// ============================================================================
// SKELETON
// ============================================================================

interface NavigationSkeletonProps {
  variant: NavigationVariant;
  size: NavigationSize;
}

const NavigationSkeleton: React.FC<NavigationSkeletonProps> = ({ variant, size }) => {
  const itemCount = variant === 'horizontal' ? 6 : 8;

  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <Skeleton className="h-8 w-8 rounded-lg" />
      <Skeleton className="h-6 w-32 rounded-lg" />
      <div className="flex-1" />
      <div className={cn(
        'flex items-center gap-2',
        variant === 'horizontal' && 'hidden lg:flex'
      )}>
        {Array.from({ length: itemCount }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-16 rounded-lg" />
        ))}
      </div>
      <Skeleton className="h-8 w-8 rounded-full" />
    </div>
  );
};

// ============================================================================
// ERROR
// ============================================================================

interface NavigationErrorProps {
  error: string;
}

const NavigationError: React.FC<NavigationErrorProps> = ({ error }) => {
  return (
    <div className="flex items-center justify-center p-4 text-red-600 dark:text-red-400">
      <ExclamationTriangleIcon className="h-5 w-5 mr-2" />
      <span>{error}</span>
    </div>
  );
};

// ============================================================================
// EXPORTS
// ============================================================================

export default NavigationMenu;

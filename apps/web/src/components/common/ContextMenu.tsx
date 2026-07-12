/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import * as ContextMenuPrimitive from '@radix-ui/react-context-menu';
import { cn } from '@/utils/helpers';
import {
  Check,
  ChevronRight,
  Dot,
  Copy,
  Cut,
  Paste,
  Trash2,
  Edit,
  Eye,
  Star,
  Share2,
  Link,
  Download,
  Upload,
  RefreshCw,
  Settings,
  Info,
  AlertCircle,
  Plus,
  Minus,
  Divide,
  X,
  CheckCircle,
  Clock,
  File,
  Folder,
  Archive,
  Printer,
  Mail,
  MessageSquare,
  User,
  Users,
  Lock,
  Unlock,
  EyeOff,
  MoreVertical,
  Move,
  Scissors,
  FilePlus,
  FolderPlus,
  FileText,
  FileImage,
  FileVideo,
  FileAudio,
  FileCode,
  FileSpreadsheet,
  FilePresentation,
  FilePdf,
  FileArchive,
} from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface ContextMenuProps
  extends React.ComponentPropsWithoutRef<typeof ContextMenuPrimitive.Root> {}

export interface ContextMenuTriggerProps
  extends React.ComponentPropsWithoutRef<typeof ContextMenuPrimitive.Trigger> {}

export interface ContextMenuGroupProps
  extends React.ComponentPropsWithoutRef<typeof ContextMenuPrimitive.Group> {}

export interface ContextMenuPortalProps
  extends React.ComponentPropsWithoutRef<typeof ContextMenuPrimitive.Portal> {}

export interface ContextMenuSubProps
  extends React.ComponentPropsWithoutRef<typeof ContextMenuPrimitive.Sub> {}

export interface ContextMenuRadioGroupProps
  extends React.ComponentPropsWithoutRef<
    typeof ContextMenuPrimitive.RadioGroup
  > {}

export interface ContextMenuContentProps
  extends React.ComponentPropsWithoutRef<typeof ContextMenuPrimitive.Content> {
  align?: 'start' | 'center' | 'end';
  sideOffset?: number;
  alignOffset?: number;
  collisionPadding?: number | { top?: number; right?: number; bottom?: number; left?: number };
  avoidCollisions?: boolean;
  sticky?: 'partial' | 'always';
  hideWhenDetached?: boolean;
}

export interface ContextMenuItemProps
  extends React.ComponentPropsWithoutRef<typeof ContextMenuPrimitive.Item> {
  inset?: boolean;
  icon?: React.ReactNode;
  shortcut?: string;
  variant?: 'default' | 'destructive' | 'success' | 'warning' | 'info';
}

export interface ContextMenuCheckboxItemProps
  extends React.ComponentPropsWithoutRef<
    typeof ContextMenuPrimitive.CheckboxItem
  > {
  inset?: boolean;
  icon?: React.ReactNode;
  shortcut?: string;
}

export interface ContextMenuRadioItemProps
  extends React.ComponentPropsWithoutRef<
    typeof ContextMenuPrimitive.RadioItem
  > {
  inset?: boolean;
  icon?: React.ReactNode;
  shortcut?: string;
}

export interface ContextMenuLabelProps
  extends React.ComponentPropsWithoutRef<typeof ContextMenuPrimitive.Label> {
  inset?: boolean;
}

export interface ContextMenuSeparatorProps
  extends React.ComponentPropsWithoutRef<
    typeof ContextMenuPrimitive.Separator
  > {}

export interface ContextMenuShortcutProps
  extends React.HTMLAttributes<HTMLSpanElement> {}

export interface ContextMenuSubTriggerProps
  extends React.ComponentPropsWithoutRef<
    typeof ContextMenuPrimitive.SubTrigger
  > {
  inset?: boolean;
  icon?: React.ReactNode;
}

export interface ContextMenuSubContentProps
  extends React.ComponentPropsWithoutRef<
    typeof ContextMenuPrimitive.SubContent
  > {
  align?: 'start' | 'center' | 'end';
  sideOffset?: number;
  alignOffset?: number;
  collisionPadding?: number | { top?: number; right?: number; bottom?: number; left?: number };
  avoidCollisions?: boolean;
}

// ============================================
// COMPOSANTS
// ============================================

const ContextMenu = ContextMenuPrimitive.Root;

const ContextMenuTrigger = ContextMenuPrimitive.Trigger;

const ContextMenuGroup = ContextMenuPrimitive.Group;

const ContextMenuPortal = ContextMenuPrimitive.Portal;

const ContextMenuSub = ContextMenuPrimitive.Sub;

const ContextMenuRadioGroup = ContextMenuPrimitive.RadioGroup;

const ContextMenuSubTrigger = React.forwardRef<
  React.ElementRef<typeof ContextMenuPrimitive.SubTrigger>,
  ContextMenuSubTriggerProps
>(({ className, inset, icon, children, ...props }, ref) => (
  <ContextMenuPrimitive.SubTrigger
    ref={ref}
    className={cn(
      'flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none',
      'focus:bg-gray-100 focus:text-gray-900 dark:focus:bg-gray-800 dark:focus:text-gray-100',
      'data-[state=open]:bg-gray-100 dark:data-[state=open]:bg-gray-800',
      inset && 'pl-8',
      className
    )}
    {...props}
  >
    {icon && <span className="mr-2 flex-shrink-0">{icon}</span>}
    <span className="flex-1">{children}</span>
    <ChevronRight className="ml-auto h-4 w-4 text-gray-400" />
  </ContextMenuPrimitive.SubTrigger>
));
ContextMenuSubTrigger.displayName = ContextMenuPrimitive.SubTrigger.displayName;

const ContextMenuSubContent = React.forwardRef<
  React.ElementRef<typeof ContextMenuPrimitive.SubContent>,
  ContextMenuSubContentProps
>(({ className, ...props }, ref) => (
  <ContextMenuPrimitive.SubContent
    ref={ref}
    className={cn(
      'z-50 min-w-[8rem] overflow-hidden rounded-md border border-gray-200 bg-white p-1 text-gray-900 shadow-md dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100',
      'data-[state=open]:animate-in data-[state=closed]:animate-out',
      'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
      'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
      'data-[side=bottom]:slide-in-from-top-2',
      'data-[side=left]:slide-in-from-right-2',
      'data-[side=right]:slide-in-from-left-2',
      'data-[side=top]:slide-in-from-bottom-2',
      className
    )}
    {...props}
  />
));
ContextMenuSubContent.displayName = ContextMenuPrimitive.SubContent.displayName;

const ContextMenuContent = React.forwardRef<
  React.ElementRef<typeof ContextMenuPrimitive.Content>,
  ContextMenuContentProps
>(({ className, ...props }, ref) => (
  <ContextMenuPrimitive.Portal>
    <ContextMenuPrimitive.Content
      ref={ref}
      className={cn(
        'z-50 min-w-[8rem] overflow-hidden rounded-md border border-gray-200 bg-white p-1 text-gray-900 shadow-md dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100',
        'data-[state=open]:animate-in data-[state=closed]:animate-out',
        'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
        'data-[side=bottom]:slide-in-from-top-2',
        'data-[side=left]:slide-in-from-right-2',
        'data-[side=right]:slide-in-from-left-2',
        'data-[side=top]:slide-in-from-bottom-2',
        className
      )}
      {...props}
    />
  </ContextMenuPrimitive.Portal>
));
ContextMenuContent.displayName = ContextMenuPrimitive.Content.displayName;

const ContextMenuItem = React.forwardRef<
  React.ElementRef<typeof ContextMenuPrimitive.Item>,
  ContextMenuItemProps
>(({ className, inset, icon, shortcut, variant = 'default', children, ...props }, ref) => {
  const variantClasses = {
    default: 'hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-gray-100 focus:bg-gray-100 focus:text-gray-900 dark:focus:bg-gray-800 dark:focus:text-gray-100',
    destructive: 'text-red-600 hover:bg-red-50 hover:text-red-700 dark:text-red-400 dark:hover:bg-red-950/50 dark:hover:text-red-300 focus:bg-red-50 focus:text-red-700 dark:focus:bg-red-950/50 dark:focus:text-red-300',
    success: 'text-green-600 hover:bg-green-50 hover:text-green-700 dark:text-green-400 dark:hover:bg-green-950/50 dark:hover:text-green-300',
    warning: 'text-yellow-600 hover:bg-yellow-50 hover:text-yellow-700 dark:text-yellow-400 dark:hover:bg-yellow-950/50 dark:hover:text-yellow-300',
    info: 'text-blue-600 hover:bg-blue-50 hover:text-blue-700 dark:text-blue-400 dark:hover:bg-blue-950/50 dark:hover:text-blue-300',
  };

  return (
    <ContextMenuPrimitive.Item
      ref={ref}
      className={cn(
        'relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none',
        'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
        inset && 'pl-8',
        variantClasses[variant],
        className
      )}
      {...props}
    >
      {icon && <span className="mr-2 flex-shrink-0">{icon}</span>}
      <span className="flex-1">{children}</span>
      {shortcut && (
        <ContextMenuShortcut>{shortcut}</ContextMenuShortcut>
      )}
    </ContextMenuPrimitive.Item>
  );
});
ContextMenuItem.displayName = ContextMenuPrimitive.Item.displayName;

const ContextMenuCheckboxItem = React.forwardRef<
  React.ElementRef<typeof ContextMenuPrimitive.CheckboxItem>,
  ContextMenuCheckboxItemProps
>(({ className, inset, icon, shortcut, children, ...props }, ref) => (
  <ContextMenuPrimitive.CheckboxItem
    ref={ref}
    className={cn(
      'relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none',
      'hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-gray-100',
      'focus:bg-gray-100 focus:text-gray-900 dark:focus:bg-gray-800 dark:focus:text-gray-100',
      'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
      inset && 'pl-8',
      className
    )}
    {...props}
  >
    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
      <ContextMenuPrimitive.ItemIndicator>
        <Check className="h-4 w-4" />
      </ContextMenuPrimitive.ItemIndicator>
    </span>
    {icon && <span className="ml-6 mr-2 flex-shrink-0">{icon}</span>}
    <span className="ml-6 flex-1">{children}</span>
    {shortcut && (
      <ContextMenuShortcut>{shortcut}</ContextMenuShortcut>
    )}
  </ContextMenuPrimitive.CheckboxItem>
));
ContextMenuCheckboxItem.displayName =
  ContextMenuPrimitive.CheckboxItem.displayName;

const ContextMenuRadioItem = React.forwardRef<
  React.ElementRef<typeof ContextMenuPrimitive.RadioItem>,
  ContextMenuRadioItemProps
>(({ className, inset, icon, shortcut, children, ...props }, ref) => (
  <ContextMenuPrimitive.RadioItem
    ref={ref}
    className={cn(
      'relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none',
      'hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-gray-100',
      'focus:bg-gray-100 focus:text-gray-900 dark:focus:bg-gray-800 dark:focus:text-gray-100',
      'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
      inset && 'pl-8',
      className
    )}
    {...props}
  >
    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
      <ContextMenuPrimitive.ItemIndicator>
        <Dot className="h-4 w-4 fill-current" />
      </ContextMenuPrimitive.ItemIndicator>
    </span>
    {icon && <span className="ml-6 mr-2 flex-shrink-0">{icon}</span>}
    <span className="ml-6 flex-1">{children}</span>
    {shortcut && (
      <ContextMenuShortcut>{shortcut}</ContextMenuShortcut>
    )}
  </ContextMenuPrimitive.RadioItem>
));
ContextMenuRadioItem.displayName = ContextMenuPrimitive.RadioItem.displayName;

const ContextMenuLabel = React.forwardRef<
  React.ElementRef<typeof ContextMenuPrimitive.Label>,
  ContextMenuLabelProps
>(({ className, inset, ...props }, ref) => (
  <ContextMenuPrimitive.Label
    ref={ref}
    className={cn(
      'px-2 py-1.5 text-sm font-semibold text-gray-900 dark:text-gray-100',
      inset && 'pl-8',
      className
    )}
    {...props}
  />
));
ContextMenuLabel.displayName = ContextMenuPrimitive.Label.displayName;

const ContextMenuSeparator = React.forwardRef<
  React.ElementRef<typeof ContextMenuPrimitive.Separator>,
  ContextMenuSeparatorProps
>(({ className, ...props }, ref) => (
  <ContextMenuPrimitive.Separator
    ref={ref}
    className={cn('-mx-1 my-1 h-px bg-gray-200 dark:bg-gray-700', className)}
    {...props}
  />
));
ContextMenuSeparator.displayName = ContextMenuPrimitive.Separator.displayName;

const ContextMenuShortcut = React.forwardRef<
  HTMLSpanElement,
  ContextMenuShortcutProps
>(({ className, ...props }, ref) => (
  <span
    ref={ref}
    className={cn(
      'ml-auto text-xs tracking-widest text-gray-400 dark:text-gray-500',
      className
    )}
    {...props}
  />
));
ContextMenuShortcut.displayName = 'ContextMenuShortcut';

// ============================================
// PRÉSÉT D'ACTIONS
// ============================================

export interface ContextMenuAction {
  label: string;
  icon?: React.ReactNode;
  shortcut?: string;
  onClick?: () => void;
  variant?: 'default' | 'destructive' | 'success' | 'warning' | 'info';
  disabled?: boolean;
}

export interface ContextMenuSection {
  label?: string;
  items: ContextMenuAction[];
}

export interface ContextMenuPresetProps {
  sections: ContextMenuSection[];
  className?: string;
}

const ContextMenuPreset = React.forwardRef<
  HTMLDivElement,
  ContextMenuPresetProps
>(({ sections, className, ...props }, ref) => {
  return (
    <ContextMenuContent ref={ref as any} className={className} {...props}>
      {sections.map((section, sectionIndex) => (
        <React.Fragment key={sectionIndex}>
          {sectionIndex > 0 && <ContextMenuSeparator />}
          {section.label && (
            <ContextMenuLabel>{section.label}</ContextMenuLabel>
          )}
          {section.items.map((item, itemIndex) => (
            <ContextMenuItem
              key={itemIndex}
              icon={item.icon}
              shortcut={item.shortcut}
              onClick={item.onClick}
              variant={item.variant}
              disabled={item.disabled}
            >
              {item.label}
            </ContextMenuItem>
          ))}
        </React.Fragment>
      ))}
    </ContextMenuContent>
  );
});
ContextMenuPreset.displayName = 'ContextMenuPreset';

// ============================================
// PRÉSÉT DÉFINIS
// ============================================

export const EDIT_ACTIONS: ContextMenuSection[] = [
  {
    items: [
      { label: 'Copier', icon: <Copy className="h-4 w-4" />, shortcut: '⌘C' },
      { label: 'Couper', icon: <Cut className="h-4 w-4" />, shortcut: '⌘X' },
      { label: 'Coller', icon: <Paste className="h-4 w-4" />, shortcut: '⌘V' },
    ],
  },
  {
    items: [
      { label: 'Modifier', icon: <Edit className="h-4 w-4" />, shortcut: '⌘E' },
      { label: 'Supprimer', icon: <Trash2 className="h-4 w-4" />, variant: 'destructive' },
    ],
  },
];

export const FILE_ACTIONS: ContextMenuSection[] = [
  {
    items: [
      { label: 'Nouveau fichier', icon: <FilePlus className="h-4 w-4" />, shortcut: '⌘N' },
      { label: 'Nouveau dossier', icon: <FolderPlus className="h-4 w-4" />, shortcut: '⌘⇧N' },
    ],
  },
  {
    items: [
      { label: 'Ouvrir', icon: <Eye className="h-4 w-4" />, shortcut: '⌘O' },
      { label: 'Partager', icon: <Share2 className="h-4 w-4" /> },
      { label: 'Télécharger', icon: <Download className="h-4 w-4" /> },
    ],
  },
  {
    items: [
      { label: 'Renommer', icon: <Edit className="h-4 w-4" /> },
      { label: 'Déplacer', icon: <Move className="h-4 w-4" /> },
      { label: 'Archiver', icon: <Archive className="h-4 w-4" /> },
      { label: 'Supprimer', icon: <Trash2 className="h-4 w-4" />, variant: 'destructive' },
    ],
  },
];

// ============================================
// EXPORTATIONS
// ============================================

export {
  ContextMenu,
  ContextMenuTrigger,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuCheckboxItem,
  ContextMenuRadioItem,
  ContextMenuLabel,
  ContextMenuSeparator,
  ContextMenuShortcut,
  ContextMenuGroup,
  ContextMenuPortal,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
  ContextMenuRadioGroup,
  ContextMenuPreset,
  EDIT_ACTIONS,
  FILE_ACTIONS,
};

export default ContextMenu;

/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import * as MenubarPrimitive from '@radix-ui/react-menubar';
import { cn } from '@/utils/helpers';
import { Check, ChevronRight, Dot } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface MenubarProps
  extends React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Root> {}

export interface MenubarMenuProps
  extends React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Menu> {}

export interface MenubarTriggerProps
  extends React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Trigger> {
  asChild?: boolean;
}

export interface MenubarContentProps
  extends React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Content> {
  align?: 'start' | 'center' | 'end';
  sideOffset?: number;
  alignOffset?: number;
  collisionPadding?: number | { top?: number; right?: number; bottom?: number; left?: number };
  avoidCollisions?: boolean;
  sticky?: 'partial' | 'always';
  hideWhenDetached?: boolean;
}

export interface MenubarItemProps
  extends React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Item> {
  inset?: boolean;
  icon?: React.ReactNode;
  shortcut?: string;
  variant?: 'default' | 'destructive' | 'success' | 'warning' | 'info';
}

export interface MenubarCheckboxItemProps
  extends React.ComponentPropsWithoutRef<typeof MenubarPrimitive.CheckboxItem> {
  inset?: boolean;
  icon?: React.ReactNode;
  shortcut?: string;
}

export interface MenubarRadioItemProps
  extends React.ComponentPropsWithoutRef<typeof MenubarPrimitive.RadioItem> {
  inset?: boolean;
  icon?: React.ReactNode;
  shortcut?: string;
}

export interface MenubarLabelProps
  extends React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Label> {
  inset?: boolean;
}

export interface MenubarSeparatorProps
  extends React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Separator> {}

export interface MenubarShortcutProps
  extends React.HTMLAttributes<HTMLSpanElement> {}

export interface MenubarSubProps
  extends React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Sub> {}

export interface MenubarSubTriggerProps
  extends React.ComponentPropsWithoutRef<typeof MenubarPrimitive.SubTrigger> {
  inset?: boolean;
  icon?: React.ReactNode;
}

export interface MenubarSubContentProps
  extends React.ComponentPropsWithoutRef<typeof MenubarPrimitive.SubContent> {
  align?: 'start' | 'center' | 'end';
  sideOffset?: number;
  alignOffset?: number;
  collisionPadding?: number | { top?: number; right?: number; bottom?: number; left?: number };
  avoidCollisions?: boolean;
}

// ============================================
// COMPOSANTS
// ============================================

const Menubar = React.forwardRef<
  React.ElementRef<typeof MenubarPrimitive.Root>,
  MenubarProps
>(({ className, ...props }, ref) => (
  <MenubarPrimitive.Root
    ref={ref}
    className={cn(
      'flex h-10 items-center space-x-1 rounded-md border border-gray-200 bg-white p-1 dark:border-gray-700 dark:bg-gray-900',
      className
    )}
    {...props}
  />
));
Menubar.displayName = MenubarPrimitive.Root.displayName;

const MenubarMenu = MenubarPrimitive.Menu;

const MenubarGroup = MenubarPrimitive.Group;

const MenubarPortal = MenubarPrimitive.Portal;

const MenubarSub = MenubarPrimitive.Sub;

const MenubarRadioGroup = MenubarPrimitive.RadioGroup;

const MenubarSubTrigger = React.forwardRef<
  React.ElementRef<typeof MenubarPrimitive.SubTrigger>,
  MenubarSubTriggerProps
>(({ className, inset, icon, children, ...props }, ref) => (
  <MenubarPrimitive.SubTrigger
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
  </MenubarPrimitive.SubTrigger>
));
MenubarSubTrigger.displayName = MenubarPrimitive.SubTrigger.displayName;

const MenubarSubContent = React.forwardRef<
  React.ElementRef<typeof MenubarPrimitive.SubContent>,
  MenubarSubContentProps
>(({ className, ...props }, ref) => (
  <MenubarPrimitive.SubContent
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
MenubarSubContent.displayName = MenubarPrimitive.SubContent.displayName;

const MenubarTrigger = React.forwardRef<
  React.ElementRef<typeof MenubarPrimitive.Trigger>,
  MenubarTriggerProps
>(({ className, ...props }, ref) => (
  <MenubarPrimitive.Trigger
    ref={ref}
    className={cn(
      'flex cursor-default select-none items-center rounded-sm px-3 py-1.5 text-sm font-medium outline-none',
      'focus:bg-gray-100 focus:text-gray-900 dark:focus:bg-gray-800 dark:focus:text-gray-100',
      'data-[state=open]:bg-gray-100 dark:data-[state=open]:bg-gray-800',
      className
    )}
    {...props}
  />
));
MenubarTrigger.displayName = MenubarPrimitive.Trigger.displayName;

const MenubarContent = React.forwardRef<
  React.ElementRef<typeof MenubarPrimitive.Content>,
  MenubarContentProps
>(({ className, align = 'start', alignOffset = 0, sideOffset = 4, ...props }, ref) => (
  <MenubarPrimitive.Portal>
    <MenubarPrimitive.Content
      ref={ref}
      align={align}
      alignOffset={alignOffset}
      sideOffset={sideOffset}
      className={cn(
        'z-50 min-w-[12rem] overflow-hidden rounded-md border border-gray-200 bg-white p-1 text-gray-900 shadow-md dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100',
        'data-[state=open]:animate-in data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
        'data-[side=bottom]:slide-in-from-top-2',
        'data-[side=left]:slide-in-from-right-2',
        'data-[side=right]:slide-in-from-left-2',
        'data-[side=top]:slide-in-from-bottom-2',
        className
      )}
      {...props}
    />
  </MenubarPrimitive.Portal>
));
MenubarContent.displayName = MenubarPrimitive.Content.displayName;

const MenubarItem = React.forwardRef<
  React.ElementRef<typeof MenubarPrimitive.Item>,
  MenubarItemProps
>(({ className, inset, icon, shortcut, variant = 'default', children, ...props }, ref) => {
  const variantClasses = {
    default: 'hover:bg-gray-100 hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-gray-100 focus:bg-gray-100 focus:text-gray-900 dark:focus:bg-gray-800 dark:focus:text-gray-100',
    destructive: 'text-red-600 hover:bg-red-50 hover:text-red-700 dark:text-red-400 dark:hover:bg-red-950/50 dark:hover:text-red-300 focus:bg-red-50 focus:text-red-700 dark:focus:bg-red-950/50 dark:focus:text-red-300',
    success: 'text-green-600 hover:bg-green-50 hover:text-green-700 dark:text-green-400 dark:hover:bg-green-950/50 dark:hover:text-green-300',
    warning: 'text-yellow-600 hover:bg-yellow-50 hover:text-yellow-700 dark:text-yellow-400 dark:hover:bg-yellow-950/50 dark:hover:text-yellow-300',
    info: 'text-blue-600 hover:bg-blue-50 hover:text-blue-700 dark:text-blue-400 dark:hover:bg-blue-950/50 dark:hover:text-blue-300',
  };

  return (
    <MenubarPrimitive.Item
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
        <MenubarShortcut>{shortcut}</MenubarShortcut>
      )}
    </MenubarPrimitive.Item>
  );
});
MenubarItem.displayName = MenubarPrimitive.Item.displayName;

const MenubarCheckboxItem = React.forwardRef<
  React.ElementRef<typeof MenubarPrimitive.CheckboxItem>,
  MenubarCheckboxItemProps
>(({ className, inset, icon, shortcut, children, ...props }, ref) => (
  <MenubarPrimitive.CheckboxItem
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
      <MenubarPrimitive.ItemIndicator>
        <Check className="h-4 w-4" />
      </MenubarPrimitive.ItemIndicator>
    </span>
    {icon && <span className="ml-6 mr-2 flex-shrink-0">{icon}</span>}
    <span className="ml-6 flex-1">{children}</span>
    {shortcut && (
      <MenubarShortcut>{shortcut}</MenubarShortcut>
    )}
  </MenubarPrimitive.CheckboxItem>
));
MenubarCheckboxItem.displayName = MenubarPrimitive.CheckboxItem.displayName;

const MenubarRadioItem = React.forwardRef<
  React.ElementRef<typeof MenubarPrimitive.RadioItem>,
  MenubarRadioItemProps
>(({ className, inset, icon, shortcut, children, ...props }, ref) => (
  <MenubarPrimitive.RadioItem
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
      <MenubarPrimitive.ItemIndicator>
        <Dot className="h-4 w-4 fill-current" />
      </MenubarPrimitive.ItemIndicator>
    </span>
    {icon && <span className="ml-6 mr-2 flex-shrink-0">{icon}</span>}
    <span className="ml-6 flex-1">{children}</span>
    {shortcut && (
      <MenubarShortcut>{shortcut}</MenubarShortcut>
    )}
  </MenubarPrimitive.RadioItem>
));
MenubarRadioItem.displayName = MenubarPrimitive.RadioItem.displayName;

const MenubarLabel = React.forwardRef<
  React.ElementRef<typeof MenubarPrimitive.Label>,
  MenubarLabelProps
>(({ className, inset, ...props }, ref) => (
  <MenubarPrimitive.Label
    ref={ref}
    className={cn(
      'px-2 py-1.5 text-sm font-semibold text-gray-900 dark:text-gray-100',
      inset && 'pl-8',
      className
    )}
    {...props}
  />
));
MenubarLabel.displayName = MenubarPrimitive.Label.displayName;

const MenubarSeparator = React.forwardRef<
  React.ElementRef<typeof MenubarPrimitive.Separator>,
  MenubarSeparatorProps
>(({ className, ...props }, ref) => (
  <MenubarPrimitive.Separator
    ref={ref}
    className={cn('-mx-1 my-1 h-px bg-gray-200 dark:bg-gray-700', className)}
    {...props}
  />
));
MenubarSeparator.displayName = MenubarPrimitive.Separator.displayName;

const MenubarShortcut = React.forwardRef<
  HTMLSpanElement,
  MenubarShortcutProps
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
MenubarShortcut.displayName = 'MenubarShortcut';

// ============================================
// EXPORTATIONS
// ============================================

export {
  Menubar,
  MenubarMenu,
  MenubarTrigger,
  MenubarContent,
  MenubarItem,
  MenubarCheckboxItem,
  MenubarRadioItem,
  MenubarLabel,
  MenubarSeparator,
  MenubarShortcut,
  MenubarGroup,
  MenubarPortal,
  MenubarSub,
  MenubarSubContent,
  MenubarSubTrigger,
  MenubarRadioGroup,
};

export default Menubar;

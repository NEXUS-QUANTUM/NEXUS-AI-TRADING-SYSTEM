/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import { cn } from '@/utils/helpers';
import { Dialog, DialogContent } from './Dialog';
import { Search, Loader2, X } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface CommandProps
  extends React.HTMLAttributes<HTMLDivElement> {
  shouldFilter?: boolean;
  filter?: (value: string, search: string) => number;
  value?: string;
  onValueChange?: (value: string) => void;
  loop?: boolean;
  children?: React.ReactNode;
}

export interface CommandDialogProps extends CommandProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  trigger?: React.ReactNode;
}

export interface CommandInputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  value?: string;
  onValueChange?: (value: string) => void;
  placeholder?: string;
  loading?: boolean;
  icon?: React.ReactNode;
}

export interface CommandListProps
  extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
}

export interface CommandEmptyProps
  extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
}

export interface CommandGroupProps
  extends React.HTMLAttributes<HTMLDivElement> {
  heading?: string;
  children?: React.ReactNode;
  forceMount?: boolean;
}

export interface CommandItemProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value?: string;
  onSelect?: (value: string) => void;
  disabled?: boolean;
  children?: React.ReactNode;
  icon?: React.ReactNode;
  shortcut?: string;
}

export interface CommandSeparatorProps
  extends React.HTMLAttributes<HTMLDivElement> {}

export interface CommandShortcutProps
  extends React.HTMLAttributes<HTMLSpanElement> {}

// ============================================
// CONTEXTE
// ============================================

interface CommandContextType {
  value: string;
  onValueChange: (value: string) => void;
  filter: (value: string, search: string) => number;
  shouldFilter: boolean;
  loop: boolean;
  selectedIndex: number;
  setSelectedIndex: (index: number) => void;
  items: Map<string, HTMLButtonElement>;
  registerItem: (id: string, element: HTMLButtonElement) => void;
  unregisterItem: (id: string) => void;
}

const CommandContext = React.createContext<CommandContextType | undefined>(
  undefined
);

const useCommand = () => {
  const context = React.useContext(CommandContext);
  if (!context) {
    throw new Error('useCommand must be used within a Command');
  }
  return context;
};

// ============================================
// HOOKS
// ============================================

const useDebounce = <T,>(value: T, delay: number): T => {
  const [debouncedValue, setDebouncedValue] = React.useState<T>(value);

  React.useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
};

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

const Command = React.forwardRef<HTMLDivElement, CommandProps>(
  (
    {
      className,
      shouldFilter = true,
      filter = (value, search) => {
        if (!search) return 1;
        return value.toLowerCase().includes(search.toLowerCase()) ? 1 : 0;
      },
      value: valueProp,
      onValueChange,
      loop = true,
      children,
      ...props
    },
    ref
  ) => {
    const [value, setValue] = React.useState(valueProp || '');
    const [selectedIndex, setSelectedIndex] = React.useState(-1);
    const [items, setItems] = React.useState<Map<string, HTMLButtonElement>>(
      new Map()
    );

    const registerItem = React.useCallback(
      (id: string, element: HTMLButtonElement) => {
        setItems((prev) => {
          const newMap = new Map(prev);
          newMap.set(id, element);
          return newMap;
        });
      },
      []
    );

    const unregisterItem = React.useCallback((id: string) => {
      setItems((prev) => {
        const newMap = new Map(prev);
        newMap.delete(id);
        return newMap;
      });
    }, []);

    const handleValueChange = (newValue: string) => {
      setValue(newValue);
      onValueChange?.(newValue);
      setSelectedIndex(-1);
    };

    const itemArray = Array.from(items.values());

    const navigate = (direction: 'up' | 'down') => {
      const total = itemArray.length;
      if (total === 0) return;

      let nextIndex: number;
      if (direction === 'down') {
        nextIndex = selectedIndex + 1;
        if (nextIndex >= total) {
          nextIndex = loop ? 0 : total - 1;
        }
      } else {
        nextIndex = selectedIndex - 1;
        if (nextIndex < 0) {
          nextIndex = loop ? total - 1 : 0;
        }
      }

      setSelectedIndex(nextIndex);
      const element = itemArray[nextIndex];
      if (element) {
        element.scrollIntoView({ block: 'nearest' });
        element.focus();
      }
    };

    const contextValue = React.useMemo(
      () => ({
        value,
        onValueChange: handleValueChange,
        filter,
        shouldFilter,
        loop,
        selectedIndex,
        setSelectedIndex,
        items,
        registerItem,
        unregisterItem,
      }),
      [
        value,
        handleValueChange,
        filter,
        shouldFilter,
        loop,
        selectedIndex,
        setSelectedIndex,
        items,
        registerItem,
        unregisterItem,
      ]
    );

    return (
      <CommandContext.Provider value={contextValue}>
        <div
          ref={ref}
          className={cn(
            'flex h-full w-full flex-col overflow-hidden rounded-md border border-gray-200 bg-white text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100',
            className
          )}
          {...props}
        >
          {children}
        </div>
      </CommandContext.Provider>
    );
  }
);
Command.displayName = 'Command';

// ============================================
// DIALOG
// ============================================

const CommandDialog = React.forwardRef<HTMLDivElement, CommandDialogProps>(
  ({ open, onOpenChange, trigger, className, children, ...props }, ref) => {
    const [internalOpen, setInternalOpen] = React.useState(false);
    const isOpen = open !== undefined ? open : internalOpen;

    const handleOpenChange = (newOpen: boolean) => {
      setInternalOpen(newOpen);
      onOpenChange?.(newOpen);
    };

    return (
      <>
        {trigger && (
          <div onClick={() => handleOpenChange(true)}>{trigger}</div>
        )}
        <Dialog open={isOpen} onOpenChange={handleOpenChange}>
          <DialogContent className="overflow-hidden p-0 max-w-2xl">
            <Command
              ref={ref}
              className="border-0 rounded-none"
              {...props}
            >
              {children}
            </Command>
          </DialogContent>
        </Dialog>
      </>
    );
  }
);
CommandDialog.displayName = 'CommandDialog';

// ============================================
// INPUT
// ============================================

const CommandInput = React.forwardRef<
  HTMLInputElement,
  CommandInputProps
>(
  (
    {
      className,
      value,
      onValueChange,
      placeholder = 'Rechercher...',
      loading = false,
      icon = <Search className="h-4 w-4" />,
      ...props
    },
    ref
  ) => {
    const { value: contextValue, onValueChange: onContextValueChange } =
      useCommand();

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = e.target.value;
      onValueChange?.(newValue);
      onContextValueChange(newValue);
    };

    const inputValue = value !== undefined ? value : contextValue;

    return (
      <div
        className={cn(
          'flex items-center gap-2 border-b border-gray-200 px-3 py-2 dark:border-gray-700',
          className
        )}
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
        ) : (
          <span className="text-gray-400">{icon}</span>
        )}
        <input
          ref={ref}
          type="text"
          value={inputValue}
          onChange={handleChange}
          placeholder={placeholder}
          className={cn(
            'flex-1 bg-transparent outline-none placeholder:text-gray-400',
            'text-sm text-gray-900 dark:text-gray-100'
          )}
          {...props}
        />
        {inputValue && (
          <button
            onClick={() => {
              onValueChange?.('');
              onContextValueChange('');
            }}
            className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-300"
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </div>
    );
  }
);
CommandInput.displayName = 'CommandInput';

// ============================================
// LIST
// ============================================

const CommandList = React.forwardRef<HTMLDivElement, CommandListProps>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex-1 overflow-y-auto overflow-x-hidden py-2 scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
);
CommandList.displayName = 'CommandList';

// ============================================
// EMPTY
// ============================================

const CommandEmpty = React.forwardRef<HTMLDivElement, CommandEmptyProps>(
  ({ className, children, ...props }, ref) => {
    const { value } = useCommand();

    if (value && children) {
      return (
        <div
          ref={ref}
          className={cn(
            'py-6 text-center text-sm text-gray-500 dark:text-gray-400',
            className
          )}
          {...props}
        >
          {children}
        </div>
      );
    }

    return null;
  }
);
CommandEmpty.displayName = 'CommandEmpty';

// ============================================
// GROUP
// ============================================

const CommandGroup = React.forwardRef<HTMLDivElement, CommandGroupProps>(
  ({ className, heading, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'overflow-hidden px-2 py-1.5',
        heading && 'border-t border-gray-200 first:border-t-0 dark:border-gray-700',
        className
      )}
      {...props}
    >
      {heading && (
        <div className="px-2 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400">
          {heading}
        </div>
      )}
      <div className="space-y-0.5">{children}</div>
    </div>
  )
);
CommandGroup.displayName = 'CommandGroup';

// ============================================
// ITEM
// ============================================

const CommandItem = React.forwardRef<
  HTMLButtonElement,
  CommandItemProps
>(
  (
    {
      className,
      value,
      onSelect,
      disabled = false,
      children,
      icon,
      shortcut,
      ...props
    },
    ref
  ) => {
    const {
      value: searchValue,
      onValueChange,
      filter,
      shouldFilter,
      selectedIndex,
      setSelectedIndex,
      registerItem,
      unregisterItem,
    } = useCommand();

    const id = React.useId();
    const itemRef = React.useRef<HTMLButtonElement>(null);

    const isSelected = selectedIndex === Array.from(registerItem as any).length - 1;

    React.useEffect(() => {
      if (itemRef.current) {
        registerItem(id, itemRef.current);
        return () => unregisterItem(id);
      }
    }, [id, registerItem, unregisterItem]);

    const shouldRender = React.useMemo(() => {
      if (!shouldFilter || !searchValue) return true;
      if (!value) return true;
      return filter(value, searchValue) > 0;
    }, [shouldFilter, searchValue, value, filter]);

    const handleSelect = () => {
      if (disabled) return;
      if (value) {
        onSelect?.(value);
        onValueChange('');
      }
    };

    if (!shouldRender) return null;

    return (
      <button
        ref={itemRef}
        className={cn(
          'flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm',
          'transition-colors duration-200',
          'hover:bg-gray-100 dark:hover:bg-gray-800',
          'focus:bg-gray-100 dark:focus:bg-gray-800',
          'data-[selected=true]:bg-gray-100 dark:data-[selected=true]:bg-gray-800',
          disabled && 'cursor-not-allowed opacity-50',
          className
        )}
        data-selected={isSelected}
        disabled={disabled}
        onClick={handleSelect}
        {...props}
      >
        {icon && <span className="flex-shrink-0">{icon}</span>}
        <span className="flex-1 text-left">{children}</span>
        {shortcut && (
          <span className="ml-auto text-xs text-gray-400">{shortcut}</span>
        )}
      </button>
    );
  }
);
CommandItem.displayName = 'CommandItem';

// ============================================
// SEPARATOR
// ============================================

const CommandSeparator = React.forwardRef<
  HTMLDivElement,
  CommandSeparatorProps
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn('-mx-1 h-px bg-gray-200 dark:bg-gray-700', className)}
    {...props}
  />
));
CommandSeparator.displayName = 'CommandSeparator';

// ============================================
// SHORTCUT
// ============================================

const CommandShortcut = React.forwardRef<
  HTMLSpanElement,
  CommandShortcutProps
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
CommandShortcut.displayName = 'CommandShortcut';

// ============================================
// EXPORTATIONS
// ============================================

export {
  Command,
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandSeparator,
  CommandShortcut,
};

export default Command;

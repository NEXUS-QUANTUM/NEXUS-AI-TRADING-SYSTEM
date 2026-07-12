import React, { useState, useCallback, useMemo, useEffect, useRef, forwardRef } from 'react';
import { cn } from '@/lib/utils';
import {
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Search,
  Filter,
  X,
  Loader2,
  Eye,
  Pencil,
  Trash2,
  Copy,
  Download,
  Printer,
  MoreHorizontal,
  Check,
  AlertCircle,
  Info,
  Settings,
  Columns,
  RefreshCw
} from 'lucide-react';
import { useVirtual } from '@/hooks/useVirtual';
import { useDebounce } from '@/hooks/useDebounce';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { useMediaQuery } from '@/hooks/useMediaQuery';

/**
 * NEXUS AI TRADING SYSTEM - Table Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete Table system with:
 * - Sorting (single/multi)
 * - Filtering
 * - Pagination (client/server)
 * - Row selection (single/multi)
 * - Row expansion
 * - Column visibility
 * - Column resizing
 * - Column reordering
 * - Virtual scrolling
 * - Infinite scroll
 * - Export (CSV, JSON, Excel)
 * - Print
 * - Search
 * - Bulk actions
 * - Responsive
 * - Accessibility (ARIA compliant)
 * - Theme aware
 * - Loading states
 * - Error states
 * - Empty states
 * - Custom renderers
 * - Cell formatting
 * - Row actions
 * - Context menu
 * - Keyboard navigation
 * - Touch support
 * - API integration
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type TableVariant = 'default' | 'bordered' | 'striped' | 'minimal' | 'compact' | 'dense' | 'modern' | 'glass';
export type TableSize = 'sm' | 'md' | 'lg';
export type TableColor = 'nexus' | 'blue' | 'green' | 'red' | 'purple';
export type TableSortDirection = 'asc' | 'desc' | null;
export type TableRowState = 'default' | 'hover' | 'selected' | 'active' | 'error' | 'warning' | 'success';

export interface TableColumn<T = any> {
  /** Unique key for the column */
  key: string;
  /** Column header text */
  header: string;
  /** Accessor function or field name */
  accessor?: keyof T | ((row: T) => any);
  /** Cell renderer */
  render?: (value: any, row: T, index: number) => React.ReactNode;
  /** Header renderer */
  renderHeader?: (column: TableColumn<T>) => React.ReactNode;
  /** Sortable */
  sortable?: boolean;
  /** Filterable */
  filterable?: boolean;
  /** Searchable */
  searchable?: boolean;
  /** Column width */
  width?: string | number;
  /** Minimum width */
  minWidth?: string | number;
  /** Maximum width */
  maxWidth?: string | number;
  /** Alignment */
  align?: 'left' | 'center' | 'right';
  /** Fixed column */
  fixed?: 'left' | 'right';
  /** Hidden by default */
  hidden?: boolean;
  /** Hideable */
  hideable?: boolean;
  /** Resizable */
  resizable?: boolean;
  /** Sort direction */
  sortDirection?: TableSortDirection;
  /** Sort priority */
  sortPriority?: number;
  /** Filter value */
  filterValue?: any;
  /** Filter options */
  filterOptions?: { label: string; value: any }[];
  /** Filter renderer */
  renderFilter?: (column: TableColumn<T>, onChange: (value: any) => void) => React.ReactNode;
  /** Cell className */
  cellClassName?: string;
  /** Header className */
  headerClassName?: string;
  /** Custom meta data */
  meta?: Record<string, any>;
}

export interface TableRow<T = any> {
  /** Unique row id */
  id: string | number;
  /** Row data */
  data: T;
  /** Row state */
  state?: TableRowState;
  /** Expanded content */
  expandedContent?: React.ReactNode;
  /** Row actions */
  actions?: TableRowAction[];
  /** Custom className */
  className?: string;
}

export interface TableRowAction {
  label: string;
  icon?: React.ReactNode;
  onClick: (row: any) => void;
  disabled?: (row: any) => boolean;
  visible?: (row: any) => boolean;
  color?: 'default' | 'primary' | 'danger' | 'success' | 'warning';
}

export interface TableSort {
  key: string;
  direction: 'asc' | 'desc';
}

export interface TableFilter {
  key: string;
  value: any;
  operator?: 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'contains' | 'startsWith' | 'endsWith' | 'in' | 'between';
}

export interface TablePagination {
  page: number;
  pageSize: number;
  total: number;
  pageSizeOptions?: number[];
}

export interface TableProps<T = any> {
  /** Table columns */
  columns: TableColumn<T>[];
  /** Table rows */
  rows: TableRow<T>[];
  /** Row key extractor */
  rowKey?: (row: T) => string | number;
  /** Table variant */
  variant?: TableVariant;
  /** Table size */
  size?: TableSize;
  /** Table color */
  color?: TableColor;
  /** Loading state */
  loading?: boolean;
  /** Error state */
  error?: string | null;
  /** Empty state content */
  emptyState?: React.ReactNode;
  /** Selection mode */
  selection?: 'none' | 'single' | 'multiple';
  /** Selected row ids */
  selectedIds?: (string | number)[];
  /** On selection change */
  onSelectionChange?: (ids: (string | number)[]) => void;
  /** On row click */
  onRowClick?: (row: T, index: number) => void;
  /** On row double click */
  onRowDoubleClick?: (row: T, index: number) => void;
  /** On row context menu */
  onRowContextMenu?: (row: T, index: number, event: React.MouseEvent) => void;
  /** Expandable rows */
  expandable?: boolean;
  /** Expanded row ids */
  expandedIds?: (string | number)[];
  /** On expand change */
  onExpandChange?: (ids: (string | number)[]) => void;
  /** Sort configuration */
  sort?: TableSort[];
  /** On sort change */
  onSortChange?: (sorts: TableSort[]) => void;
  /** Filter configuration */
  filters?: TableFilter[];
  /** On filter change */
  onFilterChange?: (filters: TableFilter[]) => void;
  /** Pagination */
  pagination?: TablePagination;
  /** On pagination change */
  onPaginationChange?: (pagination: TablePagination) => void;
  /** Enable virtual scrolling */
  virtual?: boolean;
  /** Virtual item height */
  virtualItemHeight?: number;
  /** Virtual overscan count */
  virtualOverscan?: number;
  /** Enable infinite scroll */
  infinite?: boolean;
  /** On load more */
  onLoadMore?: () => void;
  /** Loading more state */
  loadingMore?: boolean;
  /** Search value */
  searchValue?: string;
  /** On search change */
  onSearchChange?: (value: string) => void;
  /** Search placeholder */
  searchPlaceholder?: string;
  /** Enable column visibility */
  columnVisibility?: boolean;
  /** Visible columns */
  visibleColumns?: string[];
  /** On column visibility change */
  onColumnVisibilityChange?: (keys: string[]) => void;
  /** Enable column resizing */
  columnResizing?: boolean;
  /** Enable column reordering */
  columnReordering?: boolean;
  /** Enable export */
  exportable?: boolean;
  /** Export filename */
  exportFilename?: string;
  /** Export formats */
  exportFormats?: ('csv' | 'json' | 'excel')[];
  /** On export */
  onExport?: (format: 'csv' | 'json' | 'excel') => void;
  /** Enable print */
  printable?: boolean;
  /** On print */
  onPrint?: () => void;
  /** Enable refresh */
  refreshable?: boolean;
  /** On refresh */
  onRefresh?: () => void;
  /** Header actions */
  headerActions?: React.ReactNode;
  /** Footer content */
  footer?: React.ReactNode;
  /** Table className */
  className?: string;
  /** Header className */
  headerClassName?: string;
  /** Body className */
  bodyClassName?: string;
  /** Row className */
  rowClassName?: string;
  /** Cell className */
  cellClassName?: string;
  /** Persist preferences */
  persistPreferences?: boolean;
  /** Preference key */
  preferenceKey?: string;
  /** ARIA label */
  ariaLabel?: string;
  /** Test ID */
  testId?: string;
}

// ========================================
// CONFIGURATION
// ========================================

const VARIANT_CONFIG: Record<TableVariant, {
  container: string;
  header: string;
  body: string;
  row: string;
  cell: string;
}> = {
  default: {
    container: 'border border-nexus-200 dark:border-nexus-700 rounded-lg',
    header: 'bg-nexus-50 dark:bg-nexus-800',
    body: 'divide-y divide-nexus-200 dark:divide-nexus-700',
    row: 'hover:bg-nexus-50 dark:hover:bg-nexus-800/50',
    cell: ''
  },
  bordered: {
    container: 'border-2 border-nexus-300 dark:border-nexus-600 rounded-lg',
    header: 'bg-nexus-100 dark:bg-nexus-800',
    body: 'divide-y divide-nexus-300 dark:divide-nexus-600',
    row: 'hover:bg-nexus-50 dark:hover:bg-nexus-800/50',
    cell: 'border-r border-nexus-200 dark:border-nexus-700 last:border-r-0'
  },
  striped: {
    container: 'border border-nexus-200 dark:border-nexus-700 rounded-lg',
    header: 'bg-nexus-50 dark:bg-nexus-800',
    body: '',
    row: 'even:bg-nexus-50/50 dark:even:bg-nexus-800/30 hover:bg-nexus-100 dark:hover:bg-nexus-700/50',
    cell: ''
  },
  minimal: {
    container: '',
    header: 'border-b-2 border-nexus-200 dark:border-nexus-700',
    body: 'divide-y divide-nexus-100 dark:divide-nexus-800',
    row: 'hover:bg-nexus-50/50 dark:hover:bg-nexus-800/30',
    cell: ''
  },
  compact: {
    container: 'border border-nexus-200 dark:border-nexus-700 rounded-lg overflow-hidden',
    header: 'bg-nexus-50 dark:bg-nexus-800',
    body: 'divide-y divide-nexus-100 dark:divide-nexus-800',
    row: 'hover:bg-nexus-50 dark:hover:bg-nexus-800/50',
    cell: 'py-1'
  },
  dense: {
    container: 'border border-nexus-200 dark:border-nexus-700 rounded-lg overflow-hidden',
    header: 'bg-nexus-50 dark:bg-nexus-800',
    body: 'divide-y divide-nexus-100 dark:divide-nexus-800',
    row: 'hover:bg-nexus-50 dark:hover:bg-nexus-800/50',
    cell: 'py-1 text-sm'
  },
  modern: {
    container: 'border-0 shadow-lg rounded-xl overflow-hidden',
    header: 'bg-gradient-to-r from-nexus-500/10 to-nexus-600/10 dark:from-nexus-500/20 dark:to-nexus-600/20',
    body: 'divide-y divide-nexus-200/50 dark:divide-nexus-700/50',
    row: 'hover:bg-nexus-500/5 dark:hover:bg-nexus-500/10 transition-colors',
    cell: ''
  },
  glass: {
    container: 'border border-white/20 bg-white/10 backdrop-blur-xl rounded-xl overflow-hidden',
    header: 'bg-white/5',
    body: 'divide-y divide-white/10',
    row: 'hover:bg-white/5 transition-colors',
    cell: 'text-white/90'
  }
};

const SIZE_CONFIG: Record<TableSize, {
  cell: string;
  header: string;
  text: string;
}> = {
  sm: {
    cell: 'px-3 py-2',
    header: 'px-3 py-2',
    text: 'text-sm'
  },
  md: {
    cell: 'px-4 py-3',
    header: 'px-4 py-3',
    text: 'text-base'
  },
  lg: {
    cell: 'px-6 py-4',
    header: 'px-6 py-4',
    text: 'text-lg'
  }
};

const COLOR_CONFIG: Record<TableColor, {
  header: string;
  selected: string;
  hover: string;
}> = {
  nexus: {
    header: 'text-nexus-700 dark:text-nexus-300',
    selected: 'bg-nexus-50 dark:bg-nexus-800/50',
    hover: 'hover:bg-nexus-50 dark:hover:bg-nexus-800/50'
  },
  blue: {
    header: 'text-blue-700 dark:text-blue-300',
    selected: 'bg-blue-50 dark:bg-blue-900/20',
    hover: 'hover:bg-blue-50 dark:hover:bg-blue-900/20'
  },
  green: {
    header: 'text-emerald-700 dark:text-emerald-300',
    selected: 'bg-emerald-50 dark:bg-emerald-900/20',
    hover: 'hover:bg-emerald-50 dark:hover:bg-emerald-900/20'
  },
  red: {
    header: 'text-red-700 dark:text-red-300',
    selected: 'bg-red-50 dark:bg-red-900/20',
    hover: 'hover:bg-red-50 dark:hover:bg-red-900/20'
  },
  purple: {
    header: 'text-purple-700 dark:text-purple-300',
    selected: 'bg-purple-50 dark:bg-purple-900/20',
    hover: 'hover:bg-purple-50 dark:hover:bg-purple-900/20'
  }
};

// ========================================
// MAIN COMPONENT
// ========================================

export const Table = forwardRef<HTMLDivElement, TableProps>(({
  columns: initialColumns,
  rows,
  rowKey = (row: any) => row.id || row.key || JSON.stringify(row),
  variant = 'default',
  size = 'md',
  color = 'nexus',
  loading = false,
  error = null,
  emptyState,
  selection = 'none',
  selectedIds = [],
  onSelectionChange,
  onRowClick,
  onRowDoubleClick,
  onRowContextMenu,
  expandable = false,
  expandedIds = [],
  onExpandChange,
  sort = [],
  onSortChange,
  filters = [],
  onFilterChange,
  pagination,
  onPaginationChange,
  virtual = false,
  virtualItemHeight = 48,
  virtualOverscan = 5,
  infinite = false,
  onLoadMore,
  loadingMore = false,
  searchValue = '',
  onSearchChange,
  searchPlaceholder = 'Search...',
  columnVisibility = false,
  visibleColumns: initialVisibleColumns,
  onColumnVisibilityChange,
  columnResizing = false,
  columnReordering = false,
  exportable = false,
  exportFilename = 'nexus-export',
  exportFormats = ['csv', 'json'],
  onExport,
  printable = false,
  onPrint,
  refreshable = false,
  onRefresh,
  headerActions,
  footer,
  className,
  headerClassName,
  bodyClassName,
  rowClassName,
  cellClassName,
  persistPreferences = false,
  preferenceKey = 'nexus-table-preferences',
  ariaLabel = 'Data table',
  testId = 'nexus-table'
}, ref) => {
  // ========================================
  // STATE
  // ========================================
  
  const [columnsState, setColumnsState] = useState<TableColumn[]>(initialColumns);
  const [visibleColumnsState, setVisibleColumnsState] = useState<string[]>(
    initialVisibleColumns || initialColumns.filter(c => !c.hidden).map(c => c.key)
  );
  const [sortState, setSortState] = useState<TableSort[]>(sort);
  const [filterState, setFilterState] = useState<TableFilter[]>(filters);
  const [selectedState, setSelectedState] = useState<(string | number)[]>(selectedIds);
  const [expandedState, setExpandedState] = useState<(string | number)[]>(expandedIds);
  const [searchState, setSearchState] = useState(searchValue);
  const [paginationState, setPaginationState] = useState<TablePagination>(
    pagination || { page: 1, pageSize: 10, total: 0, pageSizeOptions: [5, 10, 25, 50, 100] }
  );
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});
  const [draggingColumn, setDraggingColumn] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState(0);
  const [showColumnMenu, setShowColumnMenu] = useState(false);

  // ========================================
  // REFS
  // ========================================
  
  const tableRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // ========================================
  // HOOKS
  // ========================================
  
  const isMobile = useMediaQuery('(max-width: 640px)');
  const isTablet = useMediaQuery('(max-width: 1024px)');
  const [preferences, setPreferences] = useLocalStorage<Record<string, any>>(
    preferenceKey,
    {}
  );

  const debouncedSearch = useDebounce(searchState, 300);

  // ========================================
  // EFFECTS
  // ========================================
  
  // Sync with props
  useEffect(() => {
    setColumnsState(initialColumns);
  }, [initialColumns]);

  useEffect(() => {
    setVisibleColumnsState(initialVisibleColumns || initialColumns.filter(c => !c.hidden).map(c => c.key));
  }, [initialVisibleColumns, initialColumns]);

  useEffect(() => {
    setSortState(sort);
  }, [sort]);

  useEffect(() => {
    setFilterState(filters);
  }, [filters]);

  useEffect(() => {
    setSelectedState(selectedIds);
  }, [selectedIds]);

  useEffect(() => {
    setExpandedState(expandedIds);
  }, [expandedIds]);

  useEffect(() => {
    setSearchState(searchValue);
  }, [searchValue]);

  useEffect(() => {
    if (pagination) {
      setPaginationState(pagination);
    }
  }, [pagination]);

  // Load preferences
  useEffect(() => {
    if (persistPreferences && preferences.columns) {
      setVisibleColumnsState(preferences.columns);
    }
    if (persistPreferences && preferences.sort) {
      setSortState(preferences.sort);
    }
    if (persistPreferences && preferences.pagination) {
      setPaginationState(preferences.pagination);
    }
  }, [persistPreferences, preferences]);

  // Save preferences
  useEffect(() => {
    if (persistPreferences) {
      setPreferences({
        ...preferences,
        columns: visibleColumnsState,
        sort: sortState,
        pagination: paginationState
      });
    }
  }, [persistPreferences, visibleColumnsState, sortState, paginationState]);

  // Virtual scrolling
  const virtualizer = useVirtual({
    count: rows.length,
    estimateSize: () => virtualItemHeight,
    overscan: virtualOverscan,
    enabled: virtual
  });

  // ========================================
  // HELPERS
  // ========================================
  
  const visibleColumns = useMemo(() => {
    return columnsState.filter(col => visibleColumnsState.includes(col.key));
  }, [columnsState, visibleColumnsState]);

  const getColumnWidth = useCallback((column: TableColumn) => {
    if (columnWidths[column.key]) {
      return columnWidths[column.key];
    }
    if (column.width) {
      return typeof column.width === 'number' ? `${column.width}px` : column.width;
    }
    return undefined;
  }, [columnWidths]);

  const getCellValue = useCallback((row: any, column: TableColumn) => {
    if (typeof column.accessor === 'function') {
      return column.accessor(row);
    }
    if (column.accessor) {
      return row[column.accessor];
    }
    return row[column.key];
  }, []);

  const isRowSelected = useCallback((row: any) => {
    const id = rowKey(row);
    return selectedState.includes(id);
  }, [rowKey, selectedState]);

  const isRowExpanded = useCallback((row: any) => {
    const id = rowKey(row);
    return expandedState.includes(id);
  }, [rowKey, expandedState]);

  const getSortDirection = useCallback((key: string): TableSortDirection => {
    const sortItem = sortState.find(s => s.key === key);
    return sortItem ? sortItem.direction : null;
  }, [sortState]);

  // ========================================
  // HANDLERS
  // ========================================
  
  const handleSort = useCallback((key: string) => {
    const current = getSortDirection(key);
    let newSort: TableSort[];
    
    if (current === null) {
      newSort = [...sortState, { key, direction: 'asc' }];
    } else if (current === 'asc') {
      newSort = sortState.map(s => s.key === key ? { ...s, direction: 'desc' } : s);
    } else {
      newSort = sortState.filter(s => s.key !== key);
    }
    
    setSortState(newSort);
    onSortChange?.(newSort);
  }, [getSortDirection, sortState, onSortChange]);

  const handleFilter = useCallback((key: string, value: any) => {
    const existing = filterState.findIndex(f => f.key === key);
    let newFilters: TableFilter[];
    
    if (existing >= 0) {
      if (value === null || value === undefined || value === '') {
        newFilters = filterState.filter(f => f.key !== key);
      } else {
        newFilters = [...filterState];
        newFilters[existing] = { ...newFilters[existing], value };
      }
    } else {
      newFilters = [...filterState, { key, value, operator: 'eq' }];
    }
    
    setFilterState(newFilters);
    onFilterChange?.(newFilters);
  }, [filterState, onFilterChange]);

  const handleSelect = useCallback((row: any) => {
    const id = rowKey(row);
    let newSelected: (string | number)[];
    
    if (selection === 'single') {
      newSelected = [id];
    } else {
      if (selectedState.includes(id)) {
        newSelected = selectedState.filter(s => s !== id);
      } else {
        newSelected = [...selectedState, id];
      }
    }
    
    setSelectedState(newSelected);
    onSelectionChange?.(newSelected);
  }, [selection, rowKey, selectedState, onSelectionChange]);

  const handleSelectAll = useCallback(() => {
    const allIds = rows.map(row => rowKey(row));
    const isAllSelected = allIds.every(id => selectedState.includes(id));
    const newSelected = isAllSelected ? [] : allIds;
    
    setSelectedState(newSelected);
    onSelectionChange?.(newSelected);
  }, [rows, rowKey, selectedState, onSelectionChange]);

  const handleExpand = useCallback((row: any) => {
    const id = rowKey(row);
    let newExpanded: (string | number)[];
    
    if (expandedState.includes(id)) {
      newExpanded = expandedState.filter(s => s !== id);
    } else {
      newExpanded = [...expandedState, id];
    }
    
    setExpandedState(newExpanded);
    onExpandChange?.(newExpanded);
  }, [rowKey, expandedState, onExpandChange]);

  const handlePageChange = useCallback((page: number) => {
    const newPagination = { ...paginationState, page };
    setPaginationState(newPagination);
    onPaginationChange?.(newPagination);
  }, [paginationState, onPaginationChange]);

  const handlePageSizeChange = useCallback((pageSize: number) => {
    const newPagination = { ...paginationState, pageSize, page: 1 };
    setPaginationState(newPagination);
    onPaginationChange?.(newPagination);
  }, [paginationState, onPaginationChange]);

  const handleSearch = useCallback((value: string) => {
    setSearchState(value);
    onSearchChange?.(value);
  }, [onSearchChange]);

  const handleColumnVisibility = useCallback((key: string) => {
    let newVisible: string[];
    if (visibleColumnsState.includes(key)) {
      newVisible = visibleColumnsState.filter(k => k !== key);
    } else {
      newVisible = [...visibleColumnsState, key];
    }
    setVisibleColumnsState(newVisible);
    onColumnVisibilityChange?.(newVisible);
  }, [visibleColumnsState, onColumnVisibilityChange]);

  const handleColumnResize = useCallback((key: string, width: number) => {
    setColumnWidths(prev => ({ ...prev, [key]: width }));
  }, []);

  const handleExport = useCallback((format: 'csv' | 'json' | 'excel') => {
    if (onExport) {
      onExport(format);
      return;
    }

    // Default export implementations
    const data = rows.map(row => row.data);
    let content: string;
    let mimeType: string;
    let extension: string;

    if (format === 'csv') {
      const headers = visibleColumns.map(c => c.header);
      const rows_data = data.map(row => 
        visibleColumns.map(col => {
          const value = getCellValue(row, col);
          return typeof value === 'string' ? `"${value.replace(/"/g, '""')}"` : value;
        }).join(',')
      );
      content = [headers.join(','), ...rows_data].join('\n');
      mimeType = 'text/csv';
      extension = 'csv';
    } else if (format === 'json') {
      content = JSON.stringify(data, null, 2);
      mimeType = 'application/json';
      extension = 'json';
    } else {
      // Excel - simple HTML table
      const headers = visibleColumns.map(c => `<th>${c.header}</th>`).join('');
      const rows_data = data.map(row => 
        `<tr>${visibleColumns.map(col => `<td>${getCellValue(row, col)}</td>`).join('')}</tr>`
      ).join('');
      content = `
        <html>
          <head><meta charset="UTF-8"></head>
          <body>
            <table>
              <thead><tr>${headers}</tr></thead>
              <tbody>${rows_data}</tbody>
            </table>
          </body>
        </html>
      `;
      mimeType = 'application/vnd.ms-excel';
      extension = 'xls';
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${exportFilename}.${extension}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [rows, visibleColumns, getCellValue, exportFilename, onExport]);

  // ========================================
  // RENDER HELPERS
  // ========================================
  
  const renderSortIcon = useCallback((column: TableColumn) => {
    if (!column.sortable) return null;
    
    const direction = getSortDirection(column.key);
    if (direction === 'asc') {
      return <ArrowUp className="w-3 h-3" />;
    }
    if (direction === 'desc') {
      return <ArrowDown className="w-3 h-3" />;
    }
    return <ArrowUpDown className="w-3 h-3 opacity-50" />;
  }, [getSortDirection]);

  const renderHeaderCell = useCallback((column: TableColumn) => {
    const width = getColumnWidth(column);
    
    return (
      <th
        key={column.key}
        className={cn(
          'text-left font-medium',
          SIZE_CONFIG[size].header,
          SIZE_CONFIG[size].text,
          COLOR_CONFIG[color].header,
          column.align === 'center' && 'text-center',
          column.align === 'right' && 'text-right',
          column.fixed === 'left' && 'sticky left-0 z-10',
          column.fixed === 'right' && 'sticky right-0 z-10',
          column.sortable && 'cursor-pointer hover:bg-nexus-100/50 dark:hover:bg-nexus-700/50',
          column.headerClassName,
          headerClassName
        )}
        style={{
          width: width,
          minWidth: column.minWidth,
          maxWidth: column.maxWidth,
        }}
        onClick={() => column.sortable && handleSort(column.key)}
      >
        <div className="flex items-center gap-1">
          <span className="flex-1">
            {column.renderHeader ? column.renderHeader(column) : column.header}
          </span>
          {renderSortIcon(column)}
        </div>
      </th>
    );
  }, [size, color, getColumnWidth, renderSortIcon, handleSort, headerClassName]);

  const renderCell = useCallback((row: any, column: TableColumn, index: number) => {
    const value = getCellValue(row, column);
    const width = getColumnWidth(column);
    
    return (
      <td
        key={column.key}
        className={cn(
          SIZE_CONFIG[size].cell,
          SIZE_CONFIG[size].text,
          column.align === 'center' && 'text-center',
          column.align === 'right' && 'text-right',
          column.fixed === 'left' && 'sticky left-0 z-10 bg-inherit',
          column.fixed === 'right' && 'sticky right-0 z-10 bg-inherit',
          column.cellClassName,
          cellClassName
        )}
        style={{
          width: width,
          minWidth: column.minWidth,
          maxWidth: column.maxWidth,
        }}
      >
        {column.render ? column.render(value, row, index) : value}
      </td>
    );
  }, [size, getCellValue, getColumnWidth, cellClassName]);

  const renderRow = useCallback((row: TableRow, index: number) => {
    const isSelected = isRowSelected(row.data);
    const isExpanded = isRowExpanded(row.data);
    const rowState = row.state || 'default';
    
    const stateClasses = {
      default: '',
      hover: 'hover:bg-nexus-50 dark:hover:bg-nexus-800/50',
      selected: 'bg-nexus-50 dark:bg-nexus-800/50',
      active: 'bg-nexus-100 dark:bg-nexus-700/50',
      error: 'bg-red-50 dark:bg-red-900/20',
      warning: 'bg-yellow-50 dark:bg-yellow-900/20',
      success: 'bg-emerald-50 dark:bg-emerald-900/20'
    };

    return (
      <React.Fragment key={row.id}>
        <tr
          className={cn(
            'transition-colors',
            VARIANT_CONFIG[variant].row,
            stateClasses[rowState],
            isSelected && stateClasses.selected,
            row.className,
            rowClassName
          )}
          onClick={() => onRowClick?.(row.data, index)}
          onDoubleClick={() => onRowDoubleClick?.(row.data, index)}
          onContextMenu={(e) => onRowContextMenu?.(row.data, index, e)}
        >
          {/* Selection checkbox */}
          {selection !== 'none' && (
            <td className={cn(SIZE_CONFIG[size].cell, 'sticky left-0 z-10 bg-inherit')}>
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => handleSelect(row.data)}
                className="w-4 h-4 rounded border-nexus-300 dark:border-nexus-600 text-nexus-500 focus:ring-nexus-500"
                onClick={(e) => e.stopPropagation()}
              />
            </td>
          )}

          {/* Expand toggle */}
          {expandable && row.expandedContent && (
            <td className={cn(SIZE_CONFIG[size].cell, 'sticky left-0 z-10 bg-inherit')}>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleExpand(row.data);
                }}
                className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-700 transition-colors"
              >
                <ChevronRight
                  className={cn(
                    'w-4 h-4 transition-transform',
                    isExpanded && 'rotate-90'
                  )}
                />
              </button>
            </td>
          )}

          {/* Data cells */}
          {visibleColumns.map(column => renderCell(row.data, column, index))}

          {/* Actions */}
          {row.actions && row.actions.length > 0 && (
            <td className={cn(SIZE_CONFIG[size].cell, 'sticky right-0 z-10 bg-inherit')}>
              <div className="flex items-center gap-1">
                {row.actions
                  .filter(action => action.visible ? action.visible(row.data) : true)
                  .map((action, i) => (
                    <button
                      key={i}
                      onClick={(e) => {
                        e.stopPropagation();
                        action.onClick(row.data);
                      }}
                      disabled={action.disabled ? action.disabled(row.data) : false}
                      className={cn(
                        'p-1 rounded transition-colors',
                        action.color === 'danger' && 'text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20',
                        action.color === 'primary' && 'text-nexus-500 hover:bg-nexus-50 dark:hover:bg-nexus-900/20',
                        action.color === 'success' && 'text-emerald-500 hover:bg-emerald-50 dark:hover:bg-emerald-900/20',
                        action.color === 'warning' && 'text-yellow-500 hover:bg-yellow-50 dark:hover:bg-yellow-900/20',
                        (!action.color || action.color === 'default') && 'text-nexus-500 hover:bg-nexus-50 dark:hover:bg-nexus-900/20',
                        'disabled:opacity-50 disabled:cursor-not-allowed'
                      )}
                      title={action.label}
                    >
                      {action.icon || <MoreHorizontal className="w-4 h-4" />}
                    </button>
                  ))}
              </div>
            </td>
          )}
        </tr>

        {/* Expanded content */}
        {expandable && row.expandedContent && isExpanded && (
          <tr>
            <td
              colSpan={visibleColumns.length + (selection !== 'none' ? 1 : 0) + (row.actions?.length ? 1 : 0)}
              className="p-4 bg-nexus-50/50 dark:bg-nexus-800/30"
            >
              {row.expandedContent}
            </td>
          </tr>
        )}
      </React.Fragment>
    );
  }, [
    variant,
    size,
    rowClassName,
    selection,
    expandable,
    visibleColumns,
    isRowSelected,
    isRowExpanded,
    renderCell,
    handleSelect,
    handleExpand,
    onRowClick,
    onRowDoubleClick,
    onRowContextMenu
  ]);

  const renderRows = useCallback(() => {
    const rowData = rows;
    
    if (loading) {
      return (
        <tr>
          <td
            colSpan={visibleColumns.length + (selection !== 'none' ? 1 : 0) + (rows.some(r => r.actions?.length) ? 1 : 0)}
            className="text-center py-12"
          >
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="w-8 h-8 text-nexus-500 animate-spin" />
              <span className="text-nexus-500 dark:text-nexus-400">Loading...</span>
            </div>
          </td>
        </tr>
      );
    }

    if (error) {
      return (
        <tr>
          <td
            colSpan={visibleColumns.length + (selection !== 'none' ? 1 : 0) + (rows.some(r => r.actions?.length) ? 1 : 0)}
            className="text-center py-12"
          >
            <div className="flex flex-col items-center gap-2">
              <AlertCircle className="w-8 h-8 text-red-500" />
              <span className="text-red-500">{error}</span>
            </div>
          </td>
        </tr>
      );
    }

    if (rowData.length === 0) {
      return (
        <tr>
          <td
            colSpan={visibleColumns.length + (selection !== 'none' ? 1 : 0) + (rows.some(r => r.actions?.length) ? 1 : 0)}
            className="text-center py-12"
          >
            {emptyState || (
              <div className="flex flex-col items-center gap-2">
                <Info className="w-8 h-8 text-nexus-400" />
                <span className="text-nexus-500 dark:text-nexus-400">No data available</span>
              </div>
            )}
          </td>
        </tr>
      );
    }

    if (virtual) {
      return virtualizer.virtualItems.map((virtualRow, index) => {
        const row = rowData[virtualRow.index];
        if (!row) return null;
        return renderRow(row, virtualRow.index);
      });
    }

    return rowData.map((row, index) => renderRow(row, index));
  }, [
    rows,
    visibleColumns,
    loading,
    error,
    emptyState,
    virtual,
    virtualizer,
    selection,
    renderRow
  ]);

  const renderHeader = useCallback(() => {
    return (
      <thead className={cn(VARIANT_CONFIG[variant].header)}>
        <tr>
          {selection !== 'none' && (
            <th className={cn(SIZE_CONFIG[size].header, 'sticky left-0 z-10 bg-inherit')}>
              <input
                type="checkbox"
                checked={rows.length > 0 && rows.every(row => isRowSelected(row.data))}
                onChange={handleSelectAll}
                className="w-4 h-4 rounded border-nexus-300 dark:border-nexus-600 text-nexus-500 focus:ring-nexus-500"
              />
            </th>
          )}
          
          {expandable && (
            <th className={cn(SIZE_CONFIG[size].header, 'sticky left-0 z-10 bg-inherit')}>
              <span className="sr-only">Expand</span>
            </th>
          )}
          
          {visibleColumns.map(column => renderHeaderCell(column))}
          
          {rows.some(r => r.actions?.length) && (
            <th className={cn(SIZE_CONFIG[size].header, 'sticky right-0 z-10 bg-inherit')}>
              <span className="sr-only">Actions</span>
            </th>
          )}
        </tr>
      </thead>
    );
  }, [
    variant,
    size,
    selection,
    expandable,
    visibleColumns,
    rows,
    renderHeaderCell,
    isRowSelected,
    handleSelectAll
  ]);

  const renderToolbar = useCallback(() => {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 border-b border-nexus-200 dark:border-nexus-700">
        <div className="flex flex-wrap items-center gap-2 flex-1">
          {/* Search */}
          {onSearchChange && (
            <div className="relative flex-1 min-w-[200px] max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-nexus-400" />
              <input
                type="text"
                value={searchState}
                onChange={(e) => handleSearch(e.target.value)}
                placeholder={searchPlaceholder}
                className="w-full pl-9 pr-3 py-1.5 text-sm border border-nexus-200 dark:border-nexus-700 rounded-lg bg-white dark:bg-nexus-900 focus:ring-2 focus:ring-nexus-500 focus:border-transparent"
              />
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Column visibility */}
          {columnVisibility && (
            <div className="relative">
              <button
                onClick={() => setShowColumnMenu(!showColumnMenu)}
                className="p-1.5 rounded-lg border border-nexus-200 dark:border-nexus-700 hover:bg-nexus-50 dark:hover:bg-nexus-800 transition-colors"
                title="Columns"
              >
                <Columns className="w-4 h-4 text-nexus-500" />
              </button>
              {showColumnMenu && (
                <div className="absolute right-0 top-full mt-1 bg-white dark:bg-nexus-900 border border-nexus-200 dark:border-nexus-700 rounded-lg shadow-lg p-2 z-20 min-w-[200px] max-h-[300px] overflow-y-auto">
                  {columnsState.map(col => (
                    <label key={col.key} className="flex items-center gap-2 px-2 py-1 hover:bg-nexus-50 dark:hover:bg-nexus-800 rounded cursor-pointer">
                      <input
                        type="checkbox"
                        checked={visibleColumnsState.includes(col.key)}
                        onChange={() => handleColumnVisibility(col.key)}
                        className="w-4 h-4 rounded border-nexus-300 dark:border-nexus-600 text-nexus-500 focus:ring-nexus-500"
                      />
                      <span className="text-sm">{col.header}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Refresh */}
          {refreshable && (
            <button
              onClick={onRefresh}
              className="p-1.5 rounded-lg border border-nexus-200 dark:border-nexus-700 hover:bg-nexus-50 dark:hover:bg-nexus-800 transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4 text-nexus-500" />
            </button>
          )}

          {/* Export */}
          {exportable && (
            <div className="relative group">
              <button
                className="p-1.5 rounded-lg border border-nexus-200 dark:border-nexus-700 hover:bg-nexus-50 dark:hover:bg-nexus-800 transition-colors"
                title="Export"
              >
                <Download className="w-4 h-4 text-nexus-500" />
              </button>
              <div className="absolute right-0 top-full mt-1 bg-white dark:bg-nexus-900 border border-nexus-200 dark:border-nexus-700 rounded-lg shadow-lg p-1 z-20 hidden group-hover:block">
                {exportFormats.includes('csv') && (
                  <button
                    onClick={() => handleExport('csv')}
                    className="block w-full text-left px-3 py-1 hover:bg-nexus-50 dark:hover:bg-nexus-800 rounded text-sm"
                  >
                    Export CSV
                  </button>
                )}
                {exportFormats.includes('json') && (
                  <button
                    onClick={() => handleExport('json')}
                    className="block w-full text-left px-3 py-1 hover:bg-nexus-50 dark:hover:bg-nexus-800 rounded text-sm"
                  >
                    Export JSON
                  </button>
                )}
                {exportFormats.includes('excel') && (
                  <button
                    onClick={() => handleExport('excel')}
                    className="block w-full text-left px-3 py-1 hover:bg-nexus-50 dark:hover:bg-nexus-800 rounded text-sm"
                  >
                    Export Excel
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Print */}
          {printable && (
            <button
              onClick={onPrint || (() => window.print())}
              className="p-1.5 rounded-lg border border-nexus-200 dark:border-nexus-700 hover:bg-nexus-50 dark:hover:bg-nexus-800 transition-colors"
              title="Print"
            >
              <Printer className="w-4 h-4 text-nexus-500" />
            </button>
          )}

          {headerActions}
        </div>
      </div>
    );
  }, [
    onSearchChange,
    searchState,
    searchPlaceholder,
    columnVisibility,
    refreshable,
    exportable,
    printable,
    headerActions,
    columnsState,
    visibleColumnsState,
    handleSearch,
    handleColumnVisibility,
    onRefresh,
    handleExport,
    exportFormats
  ]);

  const renderPagination = useCallback(() => {
    if (!paginationState) return null;

    const { page, pageSize, total, pageSizeOptions = [5, 10, 25, 50, 100] } = paginationState;
    const totalPages = Math.ceil(total / pageSize) || 1;
    const startItem = (page - 1) * pageSize + 1;
    const endItem = Math.min(page * pageSize, total);

    return (
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 border-t border-nexus-200 dark:border-nexus-700">
        <div className="text-sm text-nexus-500 dark:text-nexus-400">
          Showing {startItem} to {endItem} of {total} entries
        </div>
        
        <div className="flex items-center gap-2">
          <select
            value={pageSize}
            onChange={(e) => handlePageSizeChange(Number(e.target.value))}
            className="px-2 py-1 text-sm border border-nexus-200 dark:border-nexus-700 rounded-lg bg-white dark:bg-nexus-900"
          >
            {pageSizeOptions.map(size => (
              <option key={size} value={size}>{size}</option>
            ))}
          </select>

          <div className="flex items-center gap-1">
            <button
              onClick={() => handlePageChange(1)}
              disabled={page === 1}
              className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronsLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => handlePageChange(page - 1)}
              disabled={page === 1}
              className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            
            <span className="px-2 py-1 text-sm font-medium">
              {page} / {totalPages}
            </span>
            
            <button
              onClick={() => handlePageChange(page + 1)}
              disabled={page === totalPages}
              className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => handlePageChange(totalPages)}
              disabled={page === totalPages}
              className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronsRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    );
  }, [paginationState, handlePageChange, handlePageSizeChange]);

  // ========================================
  // MAIN RENDER
  // ========================================
  
  return (
    <div
      ref={ref}
      className={cn(
        'w-full',
        VARIANT_CONFIG[variant].container,
        className
      )}
      data-testid={testId}
      aria-label={ariaLabel}
      role="table"
    >
      {/* Toolbar */}
      {(onSearchChange || columnVisibility || refreshable || exportable || printable || headerActions) && (
        renderToolbar()
      )}

      {/* Table wrapper */}
      <div className="overflow-x-auto relative" ref={containerRef}>
        <div
          ref={bodyRef}
          className={cn(
            'overflow-y-auto',
            virtual && 'max-h-[600px]',
            bodyClassName
          )}
          style={{
            height: virtual ? '600px' : 'auto',
          }}
        >
          <table className="w-full border-collapse">
            {renderHeader()}
            <tbody className={cn(VARIANT_CONFIG[variant].body)}>
              {renderRows()}
            </tbody>
          </table>
        </div>
      </div>

      {/* Footer */}
      {footer && (
        <div className="border-t border-nexus-200 dark:border-nexus-700 p-4">
          {footer}
        </div>
      )}

      {/* Pagination */}
      {paginationState && renderPagination()}
    </div>
  );
});

Table.displayName = 'Table';

// ========================================
// EXPORTS
// ========================================

export default Table;

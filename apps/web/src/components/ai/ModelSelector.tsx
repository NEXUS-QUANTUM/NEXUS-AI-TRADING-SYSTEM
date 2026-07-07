/**
 * NEXUS AI TRADING SYSTEM - ModelSelector Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This component provides AI model selection functionality including:
 * - Model list display with search
 * - Model status indicators
 * - Model selection and switching
 * - Model details preview
 * - Model performance metrics
 * - Model filtering by type/status
 * - Model version management
 * - Model comparison
 * - Model activation/deactivation
 * - Model configuration preview
 * - Real-time model updates
 * - Responsive design for all devices
 */

'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Search, 
  Filter, 
  ChevronDown, 
  ChevronRight, 
  Check,
  X,
  AlertCircle,
  Info,
  Brain,
  Cpu,
  Sparkles,
  Zap,
  Clock,
  TrendingUp,
  TrendingDown,
  BarChart3,
  PieChart,
  LineChart,
  Activity,
  RefreshCw,
  Settings,
  Edit,
  Copy,
  Trash2,
  MoreVertical,
  Star,
  StarOff,
  Eye,
  EyeOff,
  Lock,
  Unlock,
  Shield,
  Award,
  Crown,
  Rocket,
  Target,
  Users,
  Calendar,
  Download,
  Upload,
  Plus,
  Minus,
  ArrowUp,
  ArrowDown,
  ArrowRight,
  ChevronLeft,
  ChevronRight as ChevronRightIcon,
  ChevronUp,
  ChevronDown as ChevronDownIcon,
} from 'lucide-react';

// Components
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Modal } from '@/components/ui/Modal';
import { Progress } from '@/components/ui/Progress';
import { Avatar } from '@/components/ui/Avatar';
import { Switch } from '@/components/ui/Switch';
import { Tooltip } from '@/components/ui/Tooltip';
import { Toast } from '@/components/ui/Toast';
import { Spinner } from '@/components/ui/Spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';

// Types
import type { AIModel, ModelMetrics, ModelStatus, ModelType } from '@/types/ai';

// Constants
import { AI_MODELS, DEFAULT_AI_CONFIG } from '@/constants/ai';

// Utils
import { formatPercentage, formatNumber, formatDate, formatTime } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

// ============================================
// Props Interface
// ============================================

interface ModelSelectorProps {
  selectedModel: AIModel | null;
  onModelChange: (model: AIModel) => void;
  models?: AIModel[];
  isLoading?: boolean;
  className?: string;
  showMetrics?: boolean;
  showSearch?: boolean;
  showFilter?: boolean;
  compact?: boolean;
  onModelCreate?: () => void;
  onModelEdit?: (model: AIModel) => void;
  onModelDelete?: (modelId: string) => void;
  onModelDuplicate?: (model: AIModel) => void;
  onModelExport?: (model: AIModel) => void;
  onModelImport?: (file: File) => void;
}

// ============================================
// Main Component
// ============================================

export function ModelSelector({
  selectedModel,
  onModelChange,
  models = AI_MODELS,
  isLoading = false,
  className,
  showMetrics = true,
  showSearch = true,
  showFilter = true,
  compact = false,
  onModelCreate,
  onModelEdit,
  onModelDelete,
  onModelDuplicate,
  onModelExport,
  onModelImport,
}: ModelSelectorProps) {
  // State
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [filterType, setFilterType] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [selectedModelDetails, setSelectedModelDetails] = useState<AIModel | null>(null);
  const [showDetails, setShowDetails] = useState<boolean>(false);
  const [showCompare, setShowCompare] = useState<boolean>(false);
  const [compareModels, setCompareModels] = useState<AIModel[]>([]);
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [showEditModal, setShowEditModal] = useState<boolean>(false);
  const [editingModel, setEditingModel] = useState<AIModel | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);
  const [deletingModelId, setDeletingModelId] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [isImporting, setIsImporting] = useState<boolean>(false);

  // Refs
  const searchInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // ============================================
  // Memoized Computations
  // ============================================

  const filteredModels = useMemo(() => {
    let result = models;

    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(model =>
        model.name.toLowerCase().includes(query) ||
        model.description.toLowerCase().includes(query) ||
        model.id.toLowerCase().includes(query)
      );
    }

    // Apply type filter
    if (filterType !== 'all') {
      result = result.filter(model => model.type === filterType);
    }

    // Apply status filter
    if (filterStatus !== 'all') {
      result = result.filter(model => model.status === filterStatus);
    }

    return result;
  }, [models, searchQuery, filterType, filterStatus]);

  const modelTypes = useMemo(() => {
    const types = new Set(models.map(model => model.type));
    return ['all', ...Array.from(types)];
  }, [models]);

  const modelStatuses = useMemo(() => {
    const statuses = new Set(models.map(model => model.status));
    return ['all', ...Array.from(statuses)];
  }, [models]);

  const getStatusColor = useCallback((status: ModelStatus) => {
    const colors: Record<ModelStatus, string> = {
      active: 'bg-green-500/20 text-green-500 border-green-500/30',
      training: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30 animate-pulse',
      idle: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
      error: 'bg-red-500/20 text-red-500 border-red-500/30',
      stopped: 'bg-blue-500/20 text-blue-500 border-blue-500/30',
      completed: 'bg-purple-500/20 text-purple-500 border-purple-500/30',
    };
    return colors[status] || colors.idle;
  }, []);

  const getTypeIcon = useCallback((type: ModelType) => {
    const icons: Record<ModelType, React.ReactNode> = {
      ensemble: <Brain className="w-4 h-4" />,
      lstm: <Cpu className="w-4 h-4" />,
      transformer: <Sparkles className="w-4 h-4" />,
      xgboost: <Target className="w-4 h-4" />,
      lightgbm: <Zap className="w-4 h-4" />,
      custom: <Settings className="w-4 h-4" />,
    };
    return icons[type] || <Brain className="w-4 h-4" />;
  }, []);

  // ============================================
  // Handlers
  // ============================================

  const handleModelSelect = useCallback((model: AIModel) => {
    onModelChange(model);
    setIsOpen(false);
    setSelectedModelDetails(null);
    setShowDetails(false);
  }, [onModelChange]);

  const handleToggleDropdown = useCallback(() => {
    setIsOpen(prev => !prev);
    if (!isOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const handleShowDetails = useCallback((model: AIModel) => {
    setSelectedModelDetails(model);
    setShowDetails(true);
  }, []);

  const handleCloseDetails = useCallback(() => {
    setShowDetails(false);
    setSelectedModelDetails(null);
  }, []);

  const handleCompare = useCallback((model: AIModel) => {
    setCompareModels(prev => {
      if (prev.some(m => m.id === model.id)) {
        return prev.filter(m => m.id !== model.id);
      }
      if (prev.length >= 3) {
        return [prev[1], prev[2], model];
      }
      return [...prev, model];
    });
  }, []);

  const handleClearCompare = useCallback(() => {
    setCompareModels([]);
    setShowCompare(false);
  }, []);

  const handleExportModel = useCallback(async (model: AIModel) => {
    setIsExporting(true);
    try {
      // In production, call API to export model
      const data = {
        ...model,
        exportedAt: new Date().toISOString(),
        version: model.version,
        config: model.config,
      };
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `model-${model.id}-${Date.now()}.json`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setShowToast({
        message: `Model "${model.name}" exported successfully!`,
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to export model.',
        type: 'error',
      });
    } finally {
      setIsExporting(false);
    }
  }, []);

  const handleImportModel = useCallback(async (file: File) => {
    setIsImporting(true);
    try {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const data = JSON.parse(e.target?.result as string);
          // Validate imported data
          if (!data.id || !data.name || !data.type) {
            throw new Error('Invalid model file');
          }
          // In production, call API to import model
          setShowToast({
            message: `Model "${data.name}" imported successfully!`,
            type: 'success',
          });
          onModelImport?.(file);
        } catch (error: any) {
          setShowToast({
            message: error.message || 'Invalid model file.',
            type: 'error',
          });
        } finally {
          setIsImporting(false);
        }
      };
      reader.readAsText(file);
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to import model.',
        type: 'error',
      });
      setIsImporting(false);
    }
  }, [onModelImport]);

  const handleDeleteModel = useCallback(async (modelId: string) => {
    setDeletingModelId(modelId);
    setShowDeleteConfirm(true);
  }, []);

  const confirmDelete = useCallback(async () => {
    if (!deletingModelId) return;
    try {
      // In production, call API to delete model
      onModelDelete?.(deletingModelId);
      setShowDeleteConfirm(false);
      setDeletingModelId(null);
      setShowToast({
        message: 'Model deleted successfully.',
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to delete model.',
        type: 'error',
      });
    }
  }, [deletingModelId, onModelDelete]);

  // ============================================
  // Toast State
  // ============================================

  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);

  // ============================================
  // Effects
  // ============================================

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ============================================
  // Render
  // ============================================

  if (compact) {
    return (
      <div className={cn("relative", className)} ref={dropdownRef}>
        <button
          onClick={handleToggleDropdown}
          className="w-full p-2 bg-gray-800 border border-gray-700 rounded-lg text-left hover:border-cyan-500 transition-colors flex items-center justify-between"
        >
          <div className="flex items-center gap-2 min-w-0">
            {selectedModel ? (
              <>
                <span className="text-cyan-400">{getTypeIcon(selectedModel.type)}</span>
                <span className="text-white truncate">{selectedModel.name}</span>
                <Badge className={cn("text-xs", getStatusColor(selectedModel.status))}>
                  {selectedModel.status}
                </Badge>
              </>
            ) : (
              <span className="text-gray-400">Select Model</span>
            )}
          </div>
          <ChevronDown className={cn(
            "w-4 h-4 text-gray-400 transition-transform",
            isOpen && "rotate-180"
          )} />
        </button>

        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="absolute z-50 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden"
            >
              <div className="p-2 space-y-1 max-h-60 overflow-y-auto">
                {isLoading ? (
                  <div className="text-center py-4">
                    <Spinner size="sm" className="mx-auto text-cyan-500" />
                  </div>
                ) : filteredModels.length > 0 ? (
                  filteredModels.map((model) => (
                    <button
                      key={model.id}
                      onClick={() => handleModelSelect(model)}
                      className={cn(
                        "w-full p-2 rounded-lg text-left transition-colors flex items-center justify-between",
                        selectedModel?.id === model.id
                          ? "bg-cyan-500/10 border border-cyan-500/30"
                          : "hover:bg-gray-700/50"
                      )}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-cyan-400">{getTypeIcon(model.type)}</span>
                        <span className="text-sm text-white truncate">{model.name}</span>
                        <Badge className={cn("text-xs", getStatusColor(model.status))}>
                          {model.status}
                        </Badge>
                      </div>
                      {selectedModel?.id === model.id && (
                        <Check className="w-4 h-4 text-cyan-400" />
                      )}
                    </button>
                  ))
                ) : (
                  <div className="text-center py-4 text-gray-500 text-sm">
                    No models found
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  }

  return (
    <div className={cn("space-y-4", className)} ref={dropdownRef}>
      {/* ============================================ */}
      {/* Header */}
      {/* ============================================ */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-cyan-400" />
          <span className="text-sm font-semibold text-gray-300">AI Models</span>
        </div>
        <div className="flex items-center gap-2">
          {onModelCreate && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onModelCreate}
              className="text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
            >
              <Plus className="w-4 h-4 mr-1" />
              New
            </Button>
          )}
          {onModelImport && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              className="text-gray-400 hover:text-white"
              isLoading={isImporting}
            >
              <Upload className="w-4 h-4" />
            </Button>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.[0]) {
                handleImportModel(e.target.files[0]);
              }
              e.target.value = '';
            }}
          />
        </div>
      </div>

      {/* ============================================ */}
      {/* Search & Filters */}
      {/* ============================================ */}
      {(showSearch || showFilter) && (
        <div className="flex flex-wrap items-center gap-2">
          {showSearch && (
            <div className="flex-1 min-w-[150px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <Input
                  ref={searchInputRef}
                  type="text"
                  placeholder="Search models..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 bg-gray-700 border-gray-600 text-white text-sm"
                />
              </div>
            </div>
          )}
          {showFilter && (
            <div className="flex items-center gap-2">
              <Select
                value={filterType}
                onValueChange={setFilterType}
                className="w-28 bg-gray-700 border-gray-600 text-sm"
              >
                <option value="all">All Types</option>
                {modelTypes.filter(t => t !== 'all').map((type) => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </Select>
              <Select
                value={filterStatus}
                onValueChange={setFilterStatus}
                className="w-28 bg-gray-700 border-gray-600 text-sm"
              >
                <option value="all">All Status</option>
                {modelStatuses.filter(s => s !== 'all').map((status) => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </Select>
            </div>
          )}
        </div>
      )}

      {/* ============================================ */}
      {/* Model List */}
      {/* ============================================ */}
      <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
        {isLoading ? (
          <div className="text-center py-8">
            <Spinner size="lg" className="mx-auto text-cyan-500" />
            <p className="text-gray-400 mt-4">Loading models...</p>
          </div>
        ) : filteredModels.length > 0 ? (
          filteredModels.map((model) => (
            <motion.div
              key={model.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
            >
              <Card
                className={cn(
                  "p-3 bg-gray-800 border-gray-700 hover:border-cyan-500/50 transition-all cursor-pointer",
                  selectedModel?.id === model.id && "border-cyan-500 bg-cyan-500/5"
                )}
              >
                <div className="flex items-start gap-3">
                  {/* Model Icon */}
                  <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center flex-shrink-0">
                    {getTypeIcon(model.type)}
                  </div>

                  {/* Model Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-white">{model.name}</span>
                      <Badge className={cn("text-xs", getStatusColor(model.status))}>
                        {model.status}
                      </Badge>
                      <Badge className="bg-gray-600 text-xs">v{model.version}</Badge>
                      {model.isDefault && (
                        <Badge className="bg-yellow-500/20 text-yellow-400 text-xs">
                          Default
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 truncate">{model.description}</p>
                    {showMetrics && (
                      <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                        <span>Accuracy: {formatPercentage(model.accuracy || 0)}</span>
                        <span>•</span>
                        <span>Predictions: {formatNumber(model.totalPredictions || 0)}</span>
                        {model.lastPrediction && (
                          <>
                            <span>•</span>
                            <span>Updated: {formatTime(model.lastPrediction)}</span>
                          </>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {selectedModel?.id !== model.id && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleModelSelect(model)}
                        className="text-cyan-400 hover:text-cyan-300"
                      >
                        <Check className="w-4 h-4" />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleShowDetails(model)}
                      className="text-gray-400 hover:text-white"
                    >
                      <Eye className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleCompare(model)}
                      className={cn(
                        "text-gray-400 hover:text-white",
                        compareModels.some(m => m.id === model.id) && "text-cyan-400"
                      )}
                    >
                      <BarChart3 className="w-4 h-4" />
                    </Button>
                    {onModelEdit && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditingModel(model);
                          setShowEditModal(true);
                        }}
                        className="text-gray-400 hover:text-white"
                      >
                        <Edit className="w-4 h-4" />
                      </Button>
                    )}
                    {onModelDuplicate && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onModelDuplicate?.(model)}
                        className="text-gray-400 hover:text-white"
                      >
                        <Copy className="w-4 h-4" />
                      </Button>
                    )}
                    {onModelExport && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleExportModel(model)}
                        isLoading={isExporting}
                        className="text-gray-400 hover:text-white"
                      >
                        <Download className="w-4 h-4" />
                      </Button>
                    )}
                    {onModelDelete && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteModel(model.id)}
                        className="text-gray-400 hover:text-red-500"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            </motion.div>
          ))
        ) : (
          <div className="text-center py-8 text-gray-500">
            <div className="text-4xl mb-3">🧠</div>
            <p>No models found</p>
            <p className="text-sm">Try adjusting your search or filters</p>
          </div>
        )}
      </div>

      {/* ============================================ */}
      {/* Compare Models Bar */}
      {/* ============================================ */}
      {compareModels.length > 0 && (
        <div className="p-3 bg-gray-700/30 rounded-lg border border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Comparing:</span>
              <div className="flex items-center gap-1">
                {compareModels.map((model) => (
                  <Badge key={model.id} className="bg-cyan-500/20 text-cyan-400 text-xs flex items-center gap-1">
                    {model.name}
                    <button
                      onClick={() => handleCompare(model)}
                      className="hover:text-red-500 ml-1"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowCompare(true)}
                className="text-cyan-400 hover:text-cyan-300"
              >
                View Comparison
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearCompare}
                className="text-gray-400 hover:text-white"
              >
                Clear
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================ */}
      {/* Model Details Modal */}
      {/* ============================================ */}
      <Modal
        open={showDetails && !!selectedModelDetails}
        onOpenChange={setShowDetails}
        title={selectedModelDetails?.name || 'Model Details'}
        className="max-w-2xl"
      >
        {selectedModelDetails && (
          <div className="space-y-4 max-h-[70vh] overflow-y-auto">
            {/* Header */}
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                {getTypeIcon(selectedModelDetails.type)}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-bold text-white">{selectedModelDetails.name}</h3>
                  <Badge className={cn("text-xs", getStatusColor(selectedModelDetails.status))}>
                    {selectedModelDetails.status}
                  </Badge>
                </div>
                <p className="text-sm text-gray-400">{selectedModelDetails.description}</p>
              </div>
            </div>

            {/* Tabs */}
            <Tabs defaultValue="overview">
              <TabsList className="bg-gray-700/30 rounded-lg p-1">
                <TabsTrigger value="overview" className="text-xs">Overview</TabsTrigger>
                <TabsTrigger value="metrics" className="text-xs">Metrics</TabsTrigger>
                <TabsTrigger value="config" className="text-xs">Configuration</TabsTrigger>
              </TabsList>

              <TabsContent value="overview" className="mt-4 space-y-3">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-gray-400">Model ID</span>
                    <div className="text-white font-mono text-xs">{selectedModelDetails.id}</div>
                  </div>
                  <div>
                    <span className="text-gray-400">Version</span>
                    <div className="text-white">v{selectedModelDetails.version}</div>
                  </div>
                  <div>
                    <span className="text-gray-400">Type</span>
                    <div className="text-white capitalize">{selectedModelDetails.type}</div>
                  </div>
                  <div>
                    <span className="text-gray-400">Created</span>
                    <div className="text-white">{formatDate(selectedModelDetails.createdAt)}</div>
                  </div>
                  {selectedModelDetails.trainingData && (
                    <>
                      <div>
                        <span className="text-gray-400">Training Data Size</span>
                        <div className="text-white">{formatNumber(selectedModelDetails.trainingData.size)}</div>
                      </div>
                      <div>
                        <span className="text-gray-400">Training Features</span>
                        <div className="text-white">{selectedModelDetails.trainingData.features?.join(', ')}</div>
                      </div>
                    </>
                  )}
                </div>
              </TabsContent>

              <TabsContent value="metrics" className="mt-4 space-y-3">
                {selectedModelDetails.accuracy !== undefined && (
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-gray-400">Accuracy</span>
                      <div className="text-green-500 font-medium">{formatPercentage(selectedModelDetails.accuracy)}</div>
                    </div>
                    <div>
                      <span className="text-gray-400">Total Predictions</span>
                      <div className="text-white">{formatNumber(selectedModelDetails.totalPredictions || 0)}</div>
                    </div>
                  </div>
                )}
                {selectedModelDetails.hyperparameters && (
                  <div className="mt-3 p-3 bg-gray-700/30 rounded-lg">
                    <span className="text-sm text-gray-400 block mb-2">Hyperparameters</span>
                    <div className="space-y-1 text-xs">
                      {Object.entries(selectedModelDetails.hyperparameters).map(([key, value]) => (
                        <div key={key} className="flex justify-between">
                          <span className="text-gray-500">{key}</span>
                          <span className="text-white font-mono">{String(value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </TabsContent>

              <TabsContent value="config" className="mt-4">
                <div className="p-3 bg-gray-700/30 rounded-lg">
                  <pre className="text-xs text-gray-300 whitespace-pre-wrap overflow-x-auto">
                    {JSON.stringify(selectedModelDetails.config, null, 2)}
                  </pre>
                </div>
              </TabsContent>
            </Tabs>

            {/* Actions */}
            <div className="flex flex-wrap gap-2 pt-4 border-t border-gray-700">
              <Button
                variant="primary"
                onClick={() => {
                  handleModelSelect(selectedModelDetails);
                  setShowDetails(false);
                }}
                className="bg-gradient-to-r from-cyan-500 to-blue-500"
              >
                Select Model
              </Button>
              {onModelEdit && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setEditingModel(selectedModelDetails);
                    setShowEditModal(true);
                    setShowDetails(false);
                  }}
                  className="border-gray-600 hover:border-cyan-500"
                >
                  <Edit className="w-4 h-4 mr-2" />
                  Edit
                </Button>
              )}
              {onModelExport && (
                <Button
                  variant="outline"
                  onClick={() => handleExportModel(selectedModelDetails)}
                  isLoading={isExporting}
                  className="border-gray-600 hover:border-cyan-500"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export
                </Button>
              )}
              {onModelDelete && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowDetails(false);
                    handleDeleteModel(selectedModelDetails.id);
                  }}
                  className="border-red-500/50 hover:border-red-500 text-red-400"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Delete
                </Button>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* ============================================ */}
      {/* Compare Models Modal */}
      {/* ============================================ */}
      <Modal
        open={showCompare && compareModels.length > 0}
        onOpenChange={setShowCompare}
        title="Model Comparison"
        className="max-w-4xl"
      >
        <div className="space-y-4 max-h-[70vh] overflow-y-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {compareModels.map((model) => (
              <Card key={model.id} className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-8 h-8 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                    {getTypeIcon(model.type)}
                  </div>
                  <div>
                    <div className="font-medium text-white">{model.name}</div>
                    <div className="text-xs text-gray-400">v{model.version}</div>
                  </div>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Status</span>
                    <Badge className={cn("text-xs", getStatusColor(model.status))}>
                      {model.status}
                    </Badge>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Accuracy</span>
                    <span className="text-green-500">{formatPercentage(model.accuracy || 0)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Predictions</span>
                    <span className="text-white">{formatNumber(model.totalPredictions || 0)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Type</span>
                    <span className="text-white capitalize">{model.type}</span>
                  </div>
                </div>
              </Card>
            ))}
          </div>
          <div className="flex justify-end">
            <Button
              variant="outline"
              onClick={handleClearCompare}
              className="border-gray-600 hover:border-gray-500"
            >
              Close Comparison
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* Edit Model Modal */}
      {/* ============================================ */}
      <Modal
        open={showEditModal && !!editingModel}
        onOpenChange={setShowEditModal}
        title="Edit Model"
        className="max-w-md"
      >
        {editingModel && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Name *</label>
              <Input
                value={editingModel.name}
                onChange={(e) => setEditingModel({ ...editingModel, name: e.target.value })}
                className="w-full bg-gray-700 border-gray-600 text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Description</label>
              <Input
                value={editingModel.description}
                onChange={(e) => setEditingModel({ ...editingModel, description: e.target.value })}
                className="w-full bg-gray-700 border-gray-600 text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Status</label>
              <Select
                value={editingModel.status}
                onValueChange={(value) => setEditingModel({ ...editingModel, status: value as ModelStatus })}
                className="w-full bg-gray-700 border-gray-600"
              >
                <option value="active">Active</option>
                <option value="idle">Idle</option>
                <option value="training">Training</option>
                <option value="stopped">Stopped</option>
                <option value="error">Error</option>
                <option value="completed">Completed</option>
              </Select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Version</label>
              <Input
                value={editingModel.version}
                onChange={(e) => setEditingModel({ ...editingModel, version: e.target.value })}
                className="w-full bg-gray-700 border-gray-600 text-white"
              />
            </div>
            <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
              <Button
                variant="outline"
                onClick={() => {
                  setShowEditModal(false);
                  setEditingModel(null);
                }}
                className="border-gray-600 hover:border-gray-500"
              >
                Cancel
              </Button>
              <Button
                onClick={() => {
                  onModelEdit?.(editingModel);
                  setShowEditModal(false);
                  setEditingModel(null);
                }}
                className="bg-gradient-to-r from-cyan-500 to-blue-500"
              >
                Save Changes
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ============================================ */}
      {/* Delete Confirmation Modal */}
      {/* ============================================ */}
      <Modal
        open={showDeleteConfirm}
        onOpenChange={setShowDeleteConfirm}
        title="Delete Model"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
            <p className="text-sm text-red-500 flex items-center gap-2">
              <AlertCircle className="w-5 h-5" />
              This action cannot be undone
            </p>
          </div>
          <p className="text-gray-400">
            Are you sure you want to delete this model? This will permanently remove it from the system.
          </p>
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
            <Button
              variant="outline"
              onClick={() => {
                setShowDeleteConfirm(false);
                setDeletingModelId(null);
              }}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDelete}
              className="bg-red-600 hover:bg-red-700"
            >
              Delete Model
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* Toast Notifications */}
      {/* ============================================ */}
      <AnimatePresence>
        {showToast && (
          <Toast
            message={showToast.message}
            type={showToast.type}
            onClose={() => setShowToast(null)}
            className="fixed bottom-4 right-4 z-50 max-w-md"
            duration={5000}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

// ============================================
// Export
// ============================================

export default ModelSelector;

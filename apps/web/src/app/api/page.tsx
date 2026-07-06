/**
 * NEXUS AI TRADING SYSTEM - API Documentation Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides comprehensive API documentation including:
 * - Interactive API explorer
 * - Endpoint documentation with examples
 * - Authentication guide
 * - WebSocket documentation
 * - Rate limiting information
 * - Error codes reference
 * - SDK and library downloads
 * - API status and health checks
 * - Usage analytics
 * - Code examples in multiple languages
 * - Request/response schemas
 * - API versioning information
 */

'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';

// Components
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Toast } from '@/components/ui/Toast';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Modal } from '@/components/ui/Modal';
import { CopyButton } from '@/components/ui/CopyButton';
import { CodeBlock } from '@/components/ui/CodeBlock';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/Accordion';

// Types
import type {
  APIEndpoint,
  APIMethod,
  APIParameter,
  APIResponse,
  APIExample,
  APISchema,
  APIAuth,
  APIRateLimit,
  APIError,
  APIVersion,
  APIWebSocket,
  APISDK,
} from '@/types/api';

// Constants
import {
  API_METHODS,
  API_AUTH_TYPES,
  API_STATUS_CODES,
  API_RATE_LIMITS,
  API_VERSIONS,
  API_CATEGORIES,
  API_EXAMPLE_LANGUAGES,
} from '@/constants/api';

// Hooks
import { useAPIExplorer } from '@/hooks/useAPIExplorer';
import { useAPIMetrics } from '@/hooks/useAPIMetrics';

// Utils
import { formatJSON, formatTimestamp, formatBytes, formatNumber } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function APIPage() {
  // Authentication
  const { user, isAuthenticated, accessToken } = useAuth();
  
  // API client
  const api = useApi();
  
  // State
  const [endpoints, setEndpoints] = useState<APIEndpoint[]>([]);
  const [selectedEndpoint, setSelectedEndpoint] = useState<APIEndpoint | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedMethod, setSelectedMethod] = useState<string>('all');
  const [selectedVersion, setSelectedVersion] = useState<string>('v1');
  const [apiStatus, setAPIStatus] = useState<any>(null);
  const [apiMetrics, setAPIMetrics] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [showToast, setShowToast] = useState<{ message: string; type: 'success' | 'error' | 'info' | 'warning' } | null>(null);
  const [activeTab, setActiveTab] = useState<string>('endpoints');
  const [showAuthModal, setShowAuthModal] = useState<boolean>(false);
  const [testEndpoint, setTestEndpoint] = useState<{
    endpoint: APIEndpoint;
    params: Record<string, any>;
    body: any;
    response: any;
    loading: boolean;
    error: string | null;
  } | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState<string>('curl');
  const [apiKey, setApiKey] = useState<string>('');
  const [showKeyModal, setShowKeyModal] = useState<boolean>(false);
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);

  // Refs
  const explorerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // ============================================
  // API Calls
  // ============================================
  
  const fetchEndpoints = useCallback(async () => {
    try {
      const response = await api.get('/api/docs/endpoints', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          version: selectedVersion,
          category: selectedCategory !== 'all' ? selectedCategory : undefined,
        },
      });
      
      if (response.data && response.data.endpoints) {
        setEndpoints(response.data.endpoints);
      }
    } catch (error) {
      console.error('Failed to fetch API endpoints:', error);
      // Fallback to default endpoints
      setEndpoints(DEFAULT_ENDPOINTS);
    }
  }, [api, accessToken, selectedVersion, selectedCategory]);

  const fetchAPIStatus = useCallback(async () => {
    try {
      const response = await api.get('/api/status');
      if (response.data) {
        setAPIStatus(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch API status:', error);
    }
  }, [api]);

  const fetchAPIMetrics = useCallback(async () => {
    try {
      const response = await api.get('/api/metrics', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      if (response.data) {
        setAPIMetrics(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch API metrics:', error);
    }
  }, [api, accessToken]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    try {
      await Promise.all([
        fetchEndpoints(),
        fetchAPIStatus(),
        fetchAPIMetrics(),
      ]);
    } catch (error) {
      console.error('Failed to fetch all data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [fetchEndpoints, fetchAPIStatus, fetchAPIMetrics]);

  // ============================================
  // Effects
  // ============================================
  
  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  useEffect(() => {
    fetchEndpoints();
  }, [selectedVersion, selectedCategory, fetchEndpoints]);

  // ============================================
  // Handlers
  // ============================================
  
  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query);
  }, []);

  const handleCategoryChange = useCallback((category: string) => {
    setSelectedCategory(category);
  }, []);

  const handleMethodChange = useCallback((method: string) => {
    setSelectedMethod(method);
  }, []);

  const handleVersionChange = useCallback((version: string) => {
    setSelectedVersion(version);
  }, []);

  const handleEndpointSelect = useCallback((endpoint: APIEndpoint) => {
    setSelectedEndpoint(endpoint);
    setTestEndpoint({
      endpoint,
      params: {},
      body: null,
      response: null,
      loading: false,
      error: null,
    });
  }, []);

  const handleTestEndpoint = useCallback(async () => {
    if (!testEndpoint) return;
    
    setTestEndpoint(prev => ({ ...prev!, loading: true, error: null }));
    
    try {
      const { endpoint, params, body } = testEndpoint;
      
      // Build URL with params
      let url = endpoint.path;
      if (params && Object.keys(params).length > 0) {
        const searchParams = new URLSearchParams();
        for (const [key, value] of Object.entries(params)) {
          if (value !== undefined && value !== null && value !== '') {
            searchParams.append(key, String(value));
          }
        }
        const queryString = searchParams.toString();
        if (queryString) {
          url += `?${queryString}`;
        }
      }
      
      // Make API call
      const method = endpoint.method.toLowerCase();
      const response = await api[method](url, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        ...(body && { data: body }),
      });
      
      setTestEndpoint(prev => ({
        ...prev!,
        loading: false,
        response: response.data,
        error: null,
      }));
      
      setShowToast({
        message: 'API request successful',
        type: 'success',
      });
    } catch (error: any) {
      setTestEndpoint(prev => ({
        ...prev!,
        loading: false,
        response: null,
        error: error.response?.data?.error || error.message || 'Request failed',
      }));
      
      setShowToast({
        message: `API request failed: ${error.message || 'Unknown error'}`,
        type: 'error',
      });
    }
  }, [testEndpoint, api, accessToken]);

  const handleGenerateAPIKey = useCallback(async () => {
    try {
      const response = await api.post('/api/keys', {}, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data && response.data.key) {
        setGeneratedKey(response.data.key);
        setShowKeyModal(true);
        setShowToast({
          message: 'API key generated successfully',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.error || 'Failed to generate API key',
        type: 'error',
      });
    }
  }, [api, accessToken]);

  const handleCopyExample = useCallback((code: string) => {
    navigator.clipboard.writeText(code);
    setShowToast({
      message: 'Code copied to clipboard',
      type: 'success',
    });
  }, []);

  // ============================================
  // Memoized Computations
  // ============================================
  
  const filteredEndpoints = useMemo(() => {
    let result = endpoints;
    
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(ep => 
        ep.path.toLowerCase().includes(query) ||
        ep.summary.toLowerCase().includes(query) ||
        ep.tags?.some(tag => tag.toLowerCase().includes(query))
      );
    }
    
    if (selectedMethod !== 'all') {
      result = result.filter(ep => ep.method === selectedMethod);
    }
    
    return result;
  }, [endpoints, searchQuery, selectedMethod]);

  const endpointCategories = useMemo(() => {
    const categories = new Set<string>();
    endpoints.forEach(ep => {
      if (ep.tags) {
        ep.tags.forEach(tag => categories.add(tag));
      }
    });
    return ['all', ...Array.from(categories)];
  }, [endpoints]);

  const getMethodColor = (method: string) => {
    const colors: Record<string, string> = {
      'GET': 'bg-green-500/20 text-green-500 border-green-500/30',
      'POST': 'bg-blue-500/20 text-blue-500 border-blue-500/30',
      'PUT': 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30',
      'PATCH': 'bg-purple-500/20 text-purple-500 border-purple-500/30',
      'DELETE': 'bg-red-500/20 text-red-500 border-red-500/30',
      'HEAD': 'bg-gray-500/20 text-gray-500 border-gray-500/30',
      'OPTIONS': 'bg-cyan-500/20 text-cyan-500 border-cyan-500/30',
    };
    return colors[method] || 'bg-gray-500/20 text-gray-500 border-gray-500/30';
  };

  // ============================================
  // Render
  // ============================================
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading API Documentation...</p>
          <p className="text-gray-500 text-sm mt-2">Fetching endpoints and schemas</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-4 md:p-6 lg:p-8">
      {/* ============================================ */}
      {/* HEADER */}
      {/* ============================================ */}
      <div className="flex flex-wrap items-center justify-between mb-8 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="text-3xl">🔗</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                API Documentation
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Complete reference for the NEXUS Trading API
              </p>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-3 flex-wrap">
          {/* API Status */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
            <div className={cn(
              'w-2 h-2 rounded-full',
              apiStatus?.status === 'operational' ? 'bg-green-500 animate-pulse' : 'bg-yellow-500'
            )} />
            <span className="text-xs text-gray-400">
              {apiStatus?.status || 'Operational'}
            </span>
          </div>
          
          {/* Version Selector */}
          <Select
            value={selectedVersion}
            onValueChange={handleVersionChange}
            className="w-24 bg-gray-800 border-gray-700 text-sm"
          >
            {API_VERSIONS.map(version => (
              <option key={version} value={version}>
                {version.toUpperCase()}
              </option>
            ))}
          </Select>
          
          {/* Generate API Key Button */}
          <Button
            onClick={handleGenerateAPIKey}
            className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
          >
            🔑 Generate API Key
          </Button>
        </div>
      </div>

      {/* ============================================ */}
      {/* API STATUS BANNER */}
      {/* ============================================ */}
      {apiStatus && (
        <div className="mb-6">
          <Card className="p-4 bg-gray-800 border-gray-700">
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              <div>
                <div className="text-xs text-gray-400">Status</div>
                <div className={cn(
                  'font-medium',
                  apiStatus.status === 'operational' ? 'text-green-500' :
                  apiStatus.status === 'degraded' ? 'text-yellow-500' : 'text-red-500'
                )}>
                  {apiStatus.status?.toUpperCase() || 'OPERATIONAL'}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Response Time</div>
                <div className="font-medium text-white">
                  {apiStatus.responseTime || 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Uptime</div>
                <div className="font-medium text-green-500">
                  {apiStatus.uptime || '99.99%'}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Requests/sec</div>
                <div className="font-medium text-cyan-400">
                  {formatNumber(apiMetrics?.requestsPerSecond || 0)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Total Requests</div>
                <div className="font-medium text-white">
                  {formatNumber(apiMetrics?.totalRequests || 0)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Error Rate</div>
                <div className="font-medium text-yellow-500">
                  {apiMetrics?.errorRate || '0.01%'}
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* ============================================ */}
      {/* MAIN TABS */}
      {/* ============================================ */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-gray-800 border border-gray-700 rounded-lg p-1 w-full overflow-x-auto">
          <TabsTrigger
            value="endpoints"
            className="data-[state=active]:bg-cyan-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📋 Endpoints
          </TabsTrigger>
          <TabsTrigger
            value="explorer"
            className="data-[state=active]:bg-blue-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🚀 API Explorer
          </TabsTrigger>
          <TabsTrigger
            value="websocket"
            className="data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🔌 WebSocket
          </TabsTrigger>
          <TabsTrigger
            value="authentication"
            className="data-[state=active]:bg-green-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🔐 Authentication
          </TabsTrigger>
          <TabsTrigger
            value="sdk"
            className="data-[state=active]:bg-orange-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📦 SDK & Libraries
          </TabsTrigger>
        </TabsList>

        {/* ========================================== */}
        {/* ENDPOINTS TAB */}
        {/* ========================================== */}
        <TabsContent value="endpoints" className="mt-4">
          <div className="grid grid-cols-12 gap-6">
            {/* Sidebar - Filters */}
            <div className="col-span-12 lg:col-span-3">
              <Card className="p-4 bg-gray-800 border-gray-700 sticky top-4">
                <div className="space-y-4">
                  {/* Search */}
                  <div>
                    <label className="text-sm text-gray-400 block mb-1">Search</label>
                    <Input
                      ref={searchInputRef}
                      type="text"
                      placeholder="Search endpoints..."
                      value={searchQuery}
                      onChange={(e) => handleSearch(e.target.value)}
                      className="w-full bg-gray-700 border-gray-600 text-white text-sm"
                    />
                  </div>
                  
                  {/* Category Filter */}
                  <div>
                    <label className="text-sm text-gray-400 block mb-1">Category</label>
                    <Select
                      value={selectedCategory}
                      onValueChange={handleCategoryChange}
                      className="w-full bg-gray-700 border-gray-600 text-sm"
                    >
                      {endpointCategories.map(cat => (
                        <option key={cat} value={cat}>
                          {cat === 'all' ? 'All Categories' : cat}
                        </option>
                      ))}
                    </Select>
                  </div>
                  
                  {/* Method Filter */}
                  <div>
                    <label className="text-sm text-gray-400 block mb-1">Method</label>
                    <Select
                      value={selectedMethod}
                      onValueChange={handleMethodChange}
                      className="w-full bg-gray-700 border-gray-600 text-sm"
                    >
                      <option value="all">All Methods</option>
                      {API_METHODS.map(method => (
                        <option key={method} value={method}>
                          {method}
                        </option>
                      ))}
                    </Select>
                  </div>
                  
                  {/* Version Info */}
                  <div className="pt-4 border-t border-gray-700">
                    <div className="text-xs text-gray-500">Current Version</div>
                    <div className="font-mono text-cyan-400">{selectedVersion.toUpperCase()}</div>
                    <div className="text-xs text-gray-500 mt-2">Base URL</div>
                    <div className="font-mono text-xs text-gray-400">
                      {process.env.NEXT_PUBLIC_API_URL || 'https://api.nexustrading.com'}
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            {/* Endpoints List */}
            <div className="col-span-12 lg:col-span-9">
              <div className="space-y-3">
                {filteredEndpoints.length > 0 ? (
                  filteredEndpoints.map((endpoint) => (
                    <motion.div
                      key={`${endpoint.path}-${endpoint.method}`}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      whileHover={{ scale: 1.01 }}
                      transition={{ duration: 0.2 }}
                    >
                      <Card 
                        className={cn(
                          'p-4 bg-gray-800 border-gray-700 hover:border-cyan-500/50 transition-all cursor-pointer',
                          selectedEndpoint?.path === endpoint.path && 
                          selectedEndpoint?.method === endpoint.method && 
                          'border-cyan-500 bg-cyan-500/5'
                        )}
                        onClick={() => handleEndpointSelect(endpoint)}
                      >
                        <div className="flex items-center gap-4">
                          <Badge className={cn('font-mono text-xs', getMethodColor(endpoint.method))}>
                            {endpoint.method}
                          </Badge>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-3">
                              <code className="text-sm text-white font-mono truncate">
                                {endpoint.path}
                              </code>
                              {endpoint.deprecated && (
                                <Badge className="bg-red-500/20 text-red-500 border-red-500/30 text-xs">
                                  Deprecated
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-gray-400 mt-1">{endpoint.summary}</p>
                          </div>
                          <div className="flex items-center gap-2">
                            {endpoint.tags?.slice(0, 2).map((tag) => (
                              <Badge key={tag} className="bg-gray-700 text-gray-300 text-xs">
                                {tag}
                              </Badge>
                            ))}
                            <div className="text-xs text-gray-500">
                              {endpoint.version || 'v1'}
                            </div>
                          </div>
                        </div>
                      </Card>
                    </motion.div>
                  ))
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    <div className="text-4xl mb-3">🔍</div>
                    <p>No endpoints found</p>
                    <p className="text-sm">Try adjusting your search or filters</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* API EXPLORER TAB */}
        {/* ========================================== */}
        <TabsContent value="explorer" className="mt-4">
          <div className="grid grid-cols-12 gap-6">
            {/* Endpoint Selection */}
            <div className="col-span-12 lg:col-span-4">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Select Endpoint</h3>
                <div className="space-y-2 max-h-[600px] overflow-y-auto">
                  {filteredEndpoints.map((endpoint) => (
                    <button
                      key={`${endpoint.path}-${endpoint.method}`}
                      onClick={() => handleEndpointSelect(endpoint)}
                      className={cn(
                        'w-full p-3 rounded-lg text-left transition-colors',
                        selectedEndpoint?.path === endpoint.path &&
                        selectedEndpoint?.method === endpoint.method
                          ? 'bg-cyan-500/20 border border-cyan-500/50'
                          : 'hover:bg-gray-700/50'
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <Badge className={cn('text-xs font-mono', getMethodColor(endpoint.method))}>
                          {endpoint.method}
                        </Badge>
                        <code className="text-xs text-white font-mono truncate">
                          {endpoint.path}
                        </code>
                      </div>
                      <p className="text-xs text-gray-400 mt-1 truncate">{endpoint.summary}</p>
                    </button>
                  ))}
                </div>
              </Card>
            </div>

            {/* Test Interface */}
            <div className="col-span-12 lg:col-span-8">
              {selectedEndpoint && testEndpoint ? (
                <Card className="p-4 bg-gray-800 border-gray-700">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <Badge className={cn('font-mono', getMethodColor(selectedEndpoint.method))}>
                        {selectedEndpoint.method}
                      </Badge>
                      <code className="text-sm text-white font-mono">{selectedEndpoint.path}</code>
                    </div>
                    <div className="flex items-center gap-2">
                      <Select
                        value={selectedLanguage}
                        onValueChange={setSelectedLanguage}
                        className="w-32 bg-gray-700 border-gray-600 text-sm"
                      >
                        {API_EXAMPLE_LANGUAGES.map(lang => (
                          <option key={lang} value={lang}>
                            {lang.toUpperCase()}
                          </option>
                        ))}
                      </Select>
                    </div>
                  </div>

                  {/* Parameters */}
                  {selectedEndpoint.parameters && selectedEndpoint.parameters.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-sm font-medium text-gray-300 mb-2">Parameters</h4>
                      <div className="space-y-2">
                        {selectedEndpoint.parameters.map((param) => (
                          <div key={param.name} className="flex items-center gap-3">
                            <div className="w-32">
                              <span className="text-sm text-cyan-400">{param.name}</span>
                              {param.required && (
                                <span className="text-red-500 text-xs ml-1">*</span>
                              )}
                            </div>
                            <div className="flex-1">
                              <Input
                                type="text"
                                placeholder={param.example || param.description}
                                value={testEndpoint.params?.[param.name] || ''}
                                onChange={(e) => {
                                  setTestEndpoint(prev => ({
                                    ...prev!,
                                    params: {
                                      ...prev?.params,
                                      [param.name]: e.target.value,
                                    },
                                  }));
                                }}
                                className="w-full bg-gray-700 border-gray-600 text-white text-sm"
                              />
                            </div>
                            <span className="text-xs text-gray-500">{param.type || 'string'}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Request Body */}
                  {selectedEndpoint.requestBody && (
                    <div className="mb-4">
                      <h4 className="text-sm font-medium text-gray-300 mb-2">Request Body</h4>
                      <textarea
                        className="w-full h-32 bg-gray-700 border-gray-600 text-white text-sm font-mono rounded-lg p-3 resize-none"
                        placeholder="JSON request body"
                        value={testEndpoint.body ? JSON.stringify(testEndpoint.body, null, 2) : selectedEndpoint.requestBody.example ? JSON.stringify(selectedEndpoint.requestBody.example, null, 2) : ''}
                        onChange={(e) => {
                          try {
                            const body = JSON.parse(e.target.value);
                            setTestEndpoint(prev => ({
                              ...prev!,
                              body,
                            }));
                          } catch {
                            // Invalid JSON, ignore
                          }
                        }}
                      />
                      <div className="text-xs text-gray-500 mt-1">
                        Content-Type: application/json
                      </div>
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="flex items-center gap-3 mb-4">
                    <Button
                      onClick={handleTestEndpoint}
                      isLoading={testEndpoint.loading}
                      className="bg-gradient-to-r from-cyan-500 to-blue-500"
                    >
                      {testEndpoint.loading ? 'Sending...' : '🚀 Send Request'}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setTestEndpoint({
                          endpoint: selectedEndpoint,
                          params: {},
                          body: null,
                          response: null,
                          loading: false,
                          error: null,
                        });
                      }}
                      className="border-gray-600 hover:border-gray-500"
                    >
                      Clear
                    </Button>
                  </div>

                  {/* Response */}
                  <div>
                    <h4 className="text-sm font-medium text-gray-300 mb-2">Response</h4>
                    <div className="bg-gray-900 rounded-lg p-4 min-h-[100px] max-h-[300px] overflow-auto">
                      {testEndpoint.loading ? (
                        <div className="flex items-center justify-center h-20">
                          <Spinner size="sm" className="text-cyan-500" />
                          <span className="ml-2 text-gray-400">Waiting for response...</span>
                        </div>
                      ) : testEndpoint.error ? (
                        <div className="text-red-500">
                          <div className="font-medium">Error</div>
                          <pre className="text-sm mt-2 whitespace-pre-wrap">{testEndpoint.error}</pre>
                        </div>
                      ) : testEndpoint.response ? (
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <Badge className="bg-green-500/20 text-green-500 border-green-500/30">
                              Success
                            </Badge>
                            <CopyButton 
                              text={JSON.stringify(testEndpoint.response, null, 2)}
                              onCopy={() => {
                                setShowToast({
                                  message: 'Response copied to clipboard',
                                  type: 'success',
                                });
                              }}
                            />
                          </div>
                          <pre className="text-sm text-gray-300 whitespace-pre-wrap">
                            {JSON.stringify(testEndpoint.response, null, 2)}
                          </pre>
                        </div>
                      ) : (
                        <div className="text-gray-500 text-center py-8">
                          <div className="text-4xl mb-2">⚡</div>
                          <p>Send a request to see the response</p>
                        </div>
                      )}
                    </div>
                    {testEndpoint.response && (
                      <div className="text-xs text-gray-500 mt-2">
                        Status: {testEndpoint.response.status || 200} • 
                        Time: {testEndpoint.response.time || 'N/A'}ms • 
                        Size: {testEndpoint.response.size ? formatBytes(testEndpoint.response.size) : 'N/A'}
                      </div>
                    )}
                  </div>
                </Card>
              ) : (
                <Card className="p-4 bg-gray-800 border-gray-700">
                  <div className="text-center py-12 text-gray-500">
                    <div className="text-6xl mb-4">🚀</div>
                    <p className="text-lg font-medium">Select an endpoint to test</p>
                    <p className="text-sm">Choose an endpoint from the list on the left</p>
                  </div>
                </Card>
              )}
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* WEBSOCKET TAB */}
        {/* ========================================== */}
        <TabsContent value="websocket" className="mt-4">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                  <span className="text-purple-400">🔌</span> WebSocket Connection
                </h3>
                <div className="space-y-4">
                  <div>
                    <div className="text-xs text-gray-500 mb-1">WebSocket URL</div>
                    <code className="text-sm text-cyan-400 font-mono bg-gray-900 p-2 rounded block">
                      wss://api.nexustrading.com/websocket
                    </code>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Authentication</div>
                    <code className="text-sm text-gray-300 font-mono bg-gray-900 p-2 rounded block">
                      {`{
  "type": "auth",
  "data": {
    "token": "YOUR_JWT_TOKEN"
  }
}`}
                    </code>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Subscribe to Channel</div>
                    <code className="text-sm text-gray-300 font-mono bg-gray-900 p-2 rounded block">
                      {`{
  "type": "subscribe",
  "data": {
    "channel": "market_data",
    "symbol": "BTC-USD"
  }
}`}
                    </code>
                  </div>
                  <div className="pt-4 border-t border-gray-700">
                    <h4 className="text-sm font-medium text-gray-300 mb-2">Available Channels</h4>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-gray-900 p-2 rounded">
                        <div className="text-xs text-cyan-400">market_data</div>
                        <div className="text-xs text-gray-500">Real-time price data</div>
                      </div>
                      <div className="bg-gray-900 p-2 rounded">
                        <div className="text-xs text-cyan-400">ai_predictions</div>
                        <div className="text-xs text-gray-500">AI trading signals</div>
                      </div>
                      <div className="bg-gray-900 p-2 rounded">
                        <div className="text-xs text-cyan-400">portfolio</div>
                        <div className="text-xs text-gray-500">Portfolio updates</div>
                      </div>
                      <div className="bg-gray-900 p-2 rounded">
                        <div className="text-xs text-cyan-400">alerts</div>
                        <div className="text-xs text-gray-500">Alert notifications</div>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                  <span className="text-green-400">📡</span> Connection Status
                </h3>
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-gray-500"></div>
                      <span className="text-sm text-gray-400">Disconnected</span>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-gray-600 hover:border-cyan-500"
                    >
                      Connect
                    </Button>
                  </div>
                  <div className="bg-gray-900 rounded-lg p-4 h-40 overflow-y-auto">
                    <div className="text-xs text-gray-500 text-center py-8">
                      <p>Connect to WebSocket to see live messages</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Input
                      placeholder="Send message..."
                      className="flex-1 bg-gray-700 border-gray-600 text-white text-sm"
                    />
                    <Button variant="primary" size="sm" disabled>
                      Send
                    </Button>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* AUTHENTICATION TAB */}
        {/* ========================================== */}
        <TabsContent value="authentication" className="mt-4">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                  <span className="text-green-400">🔐</span> Authentication Methods
                </h3>
                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium text-white mb-2">JWT Authentication</h4>
                    <div className="bg-gray-900 p-3 rounded">
                      <div className="text-xs text-gray-500 mb-1">Header</div>
                      <code className="text-sm text-cyan-400 font-mono">
                        Authorization: Bearer YOUR_JWT_TOKEN
                      </code>
                    </div>
                    <p className="text-xs text-gray-400 mt-2">
                      JWT tokens are obtained through the login endpoint and expire after 24 hours.
                    </p>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-white mb-2">API Key Authentication</h4>
                    <div className="bg-gray-900 p-3 rounded">
                      <div className="text-xs text-gray-500 mb-1">Header</div>
                      <code className="text-sm text-cyan-400 font-mono">
                        X-API-Key: YOUR_API_KEY
                      </code>
                    </div>
                    <p className="text-xs text-gray-400 mt-2">
                      API keys are persistent and can be generated from the dashboard.
                    </p>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-white mb-2">OAuth 2.0</h4>
                    <div className="bg-gray-900 p-3 rounded">
                      <div className="text-xs text-gray-500 mb-1">Authorization URL</div>
                      <code className="text-sm text-cyan-400 font-mono block">
                        https://api.nexustrading.com/oauth/authorize
                      </code>
                      <div className="text-xs text-gray-500 mt-2 mb-1">Token URL</div>
                      <code className="text-sm text-cyan-400 font-mono block">
                        https://api.nexustrading.com/oauth/token
                      </code>
                    </div>
                    <p className="text-xs text-gray-400 mt-2">
                      OAuth 2.0 with authorization code flow for third-party applications.
                    </p>
                  </div>
                </div>
              </Card>
            </div>

            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                  <span className="text-yellow-400">📋</span> Rate Limits
                </h3>
                <div className="space-y-4">
                  <div className="bg-gray-900 p-3 rounded">
                    <div className="flex justify-between">
                      <span className="text-xs text-gray-500">Free Tier</span>
                      <span className="text-xs text-white">60 requests/min</span>
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="text-xs text-gray-500">Pro Tier</span>
                      <span className="text-xs text-white">300 requests/min</span>
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="text-xs text-gray-500">Enterprise</span>
                      <span className="text-xs text-white">Unlimited</span>
                    </div>
                  </div>
                  <div className="bg-gray-900 p-3 rounded">
                    <div className="text-xs text-gray-500 mb-1">Rate Limit Headers</div>
                    <code className="text-xs text-gray-300 font-mono block">
                      X-RateLimit-Limit: 60
                    </code>
                    <code className="text-xs text-gray-300 font-mono block">
                      X-RateLimit-Remaining: 45
                    </code>
                    <code className="text-xs text-gray-300 font-mono block">
                      X-RateLimit-Reset: 1640995200
                    </code>
                  </div>
                  <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
                    <p className="text-xs text-yellow-400">
                      ⚠️ Rate limits are per API key. Exceeding limits will result in 429 responses.
                    </p>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* SDK TAB */}
        {/* ========================================== */}
        <TabsContent value="sdk" className="mt-4">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                  <span className="text-orange-400">📦</span> SDK & Libraries
                </h3>
                <div className="space-y-4">
                  {/* Python SDK */}
                  <div className="bg-gray-900 p-4 rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="text-2xl">🐍</div>
                        <div>
                          <div className="text-white font-medium">Python SDK</div>
                          <div className="text-xs text-gray-500">nexus-trading-python</div>
                        </div>
                      </div>
                      <Badge className="bg-blue-500/20 text-blue-500 border-blue-500/30">
                        v2.1.0
                      </Badge>
                    </div>
                    <div className="mt-3">
                      <CopyButton text="pip install nexus-trading-python">
                        <code className="text-sm text-cyan-400 font-mono bg-gray-800 p-2 rounded block">
                          pip install nexus-trading-python
                        </code>
                      </CopyButton>
                    </div>
                    <div className="mt-2">
                      <CodeBlock language="python">
                        {`from nexus import NexusTrading

# Initialize client
client = NexusTrading(api_key="YOUR_API_KEY")

# Get market data
data = client.market_data.get("BTC-USD")

# Get AI prediction
prediction = client.ai.predict("BTC-USD", timeframe="1h")

# Execute trade
trade = client.trading.execute_order(
    symbol="BTC-USD",
    side="buy",
    amount=0.001
)`}
                      </CodeBlock>
                    </div>
                  </div>

                  {/* JavaScript/TypeScript SDK */}
                  <div className="bg-gray-900 p-4 rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="text-2xl">📘</div>
                        <div>
                          <div className="text-white font-medium">JavaScript/TypeScript SDK</div>
                          <div className="text-xs text-gray-500">@nexus/trading-sdk</div>
                        </div>
                      </div>
                      <Badge className="bg-blue-500/20 text-blue-500 border-blue-500/30">
                        v2.1.0
                      </Badge>
                    </div>
                    <div className="mt-3">
                      <CopyButton text="npm install @nexus/trading-sdk">
                        <code className="text-sm text-cyan-400 font-mono bg-gray-800 p-2 rounded block">
                          npm install @nexus/trading-sdk
                        </code>
                      </CopyButton>
                    </div>
                    <div className="mt-2">
                      <CodeBlock language="javascript">
                        {`import { NexusTrading } from '@nexus/trading-sdk';

// Initialize client
const client = new NexusTrading({
  apiKey: 'YOUR_API_KEY'
});

// Get market data
const data = await client.marketData.get('BTC-USD');

// Get AI prediction
const prediction = await client.ai.predict({
  symbol: 'BTC-USD',
  timeframe: '1h'
});

// Execute trade
const trade = await client.trading.executeOrder({
  symbol: 'BTC-USD',
  side: 'buy',
  amount: 0.001
});`}
                      </CodeBlock>
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                  <span className="text-purple-400">📄</span> Resources
                </h3>
                <div className="space-y-4">
                  <div className="bg-gray-900 p-4 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="text-2xl">📖</div>
                      <div>
                        <div className="text-white font-medium">API Reference</div>
                        <div className="text-xs text-gray-500">Complete API documentation</div>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-3 border-gray-600 hover:border-cyan-500"
                      onClick={() => window.open('/api/docs', '_blank')}
                    >
                      View Documentation
                    </Button>
                  </div>

                  <div className="bg-gray-900 p-4 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="text-2xl">💡</div>
                      <div>
                        <div className="text-white font-medium">Examples</div>
                        <div className="text-xs text-gray-500">Code examples and tutorials</div>
                      </div>
                    </div>
                    <div className="flex gap-2 mt-3">
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-gray-600 hover:border-cyan-500"
                        onClick={() => window.open('/api/examples', '_blank')}
                      >
                        View Examples
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-gray-600 hover:border-cyan-500"
                        onClick={() => window.open('https://github.com/NEXUS-QUANTUM/examples', '_blank')}
                      >
                        GitHub
                      </Button>
                    </div>
                  </div>

                  <div className="bg-gray-900 p-4 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="text-2xl">🆘</div>
                      <div>
                        <div className="text-white font-medium">Support</div>
                        <div className="text-xs text-gray-500">Get help with the API</div>
                      </div>
                    </div>
                    <div className="flex gap-2 mt-3">
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-gray-600 hover:border-cyan-500"
                        onClick={() => window.open('/support', '_blank')}
                      >
                        Support Center
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-gray-600 hover:border-cyan-500"
                        onClick={() => window.open('https://discord.gg/nexus', '_blank')}
                      >
                        Discord
                      </Button>
                    </div>
                  </div>

                  <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                    <p className="text-xs text-green-400">
                      ✅ All SDKs are open source and available on GitHub
                    </p>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* ============================================ */}
      {/* GENERATE API KEY MODAL */}
      {/* ============================================ */}
      <Modal
        open={showKeyModal}
        onOpenChange={setShowKeyModal}
        title="API Key Generated"
        className="max-w-lg"
      >
        <div className="space-y-4">
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
            <p className="text-xs text-yellow-400">
              ⚠️ Save this key now. It will not be shown again!
            </p>
          </div>
          <div className="bg-gray-900 p-4 rounded-lg">
            <code className="text-sm text-cyan-400 font-mono break-all">
              {generatedKey}
            </code>
          </div>
          <div className="flex gap-3">
            <CopyButton text={generatedKey || ''}>
              <Button variant="primary" className="flex-1 bg-cyan-500 hover:bg-cyan-600">
                📋 Copy Key
              </Button>
            </CopyButton>
            <Button
              variant="outline"
              onClick={() => setShowKeyModal(false)}
              className="flex-1 border-gray-600 hover:border-gray-500"
            >
              Close
            </Button>
          </div>
          <div className="text-xs text-gray-500">
            Use this key in the Authorization header: <code className="text-cyan-400">X-API-Key: {generatedKey?.slice(0, 20)}...</code>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* TOAST NOTIFICATIONS */}
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
// Default Data
// ============================================

const DEFAULT_ENDPOINTS: APIEndpoint[] = [
  {
    path: '/api/v1/market/data',
    method: 'GET',
    summary: 'Get real-time market data',
    tags: ['Market Data', 'Real-time'],
    version: 'v1',
    parameters: [
      { name: 'symbol', type: 'string', required: true, description: 'Trading symbol', example: 'BTC-USD' },
      { name: 'timeframe', type: 'string', required: false, description: 'Timeframe', example: '1h' },
    ],
  },
  {
    path: '/api/v1/ai/predictions',
    method: 'GET',
    summary: 'Get AI trading predictions',
    tags: ['AI', 'Predictions'],
    version: 'v1',
    parameters: [
      { name: 'symbol', type: 'string', required: true, description: 'Trading symbol', example: 'BTC-USD' },
      { name: 'model', type: 'string', required: false, description: 'Model ID', example: 'ensemble-pro-v3' },
    ],
  },
  {
    path: '/api/v1/trading/orders',
    method: 'POST',
    summary: 'Execute trading order',
    tags: ['Trading', 'Orders'],
    version: 'v1',
    requestBody: {
      properties: {
        symbol: { type: 'string', required: true, example: 'BTC-USD' },
        side: { type: 'string', required: true, example: 'buy' },
        amount: { type: 'number', required: true, example: 0.001 },
        type: { type: 'string', required: false, example: 'market' },
      },
    },
  },
  {
    path: '/api/v1/portfolio',
    method: 'GET',
    summary: 'Get portfolio information',
    tags: ['Portfolio', 'Account'],
    version: 'v1',
    parameters: [],
  },
  {
    path: '/api/v1/alerts',
    method: 'POST',
    summary: 'Create price alert',
    tags: ['Alerts'],
    version: 'v1',
    requestBody: {
      properties: {
        symbol: { type: 'string', required: true, example: 'BTC-USD' },
        condition: { type: 'string', required: true, example: 'above' },
        value: { type: 'number', required: true, example: 50000 },
      },
    },
  },
  {
    path: '/api/v1/analytics/metrics',
    method: 'GET',
    summary: 'Get analytics metrics',
    tags: ['Analytics', 'Metrics'],
    version: 'v1',
    parameters: [
      { name: 'timeframe', type: 'string', required: false, description: 'Timeframe', example: '1M' },
      { name: 'symbol', type: 'string', required: false, description: 'Trading symbol', example: 'BTC-USD' },
    ],
  },
];

export const API_VERSIONS = ['v1', 'v2', 'v3'];
export const API_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];
export const API_EXAMPLE_LANGUAGES = ['curl', 'python', 'javascript', 'typescript'];

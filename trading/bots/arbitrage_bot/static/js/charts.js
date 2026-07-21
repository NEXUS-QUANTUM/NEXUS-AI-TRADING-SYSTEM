/**
 * NEXUS AI TRADING SYSTEM - Arbitrage Bot Charts Module
 * Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
 * @version 1.0.0
 * @author NEXUS QUANTUM TEAM
 */

import Chart from 'chart.js/auto';
import 'chartjs-adapter-date-fns';
import { fr, enUS } from 'date-fns/locale';

// ============================================================
// CORE CONFIGURATION
// ============================================================

const CONFIG = {
    colors: {
        primary: '#00D4AA',
        secondary: '#FF6B6B',
        success: '#00D4AA',
        warning: '#FFB74D',
        danger: '#FF6B6B',
        info: '#4FC3F7',
        dark: '#1A1A2E',
        darkBg: '#16213E',
        cardBg: 'rgba(26, 26, 46, 0.85)',
        gridColor: 'rgba(255, 255, 255, 0.06)',
        textColor: '#E0E0E0',
        profit: '#00D4AA',
        loss: '#FF6B6B',
    },
    gradients: {
        profit: ['rgba(0, 212, 170, 0.2)', 'rgba(0, 212, 170, 0.05)'],
        loss: ['rgba(255, 107, 107, 0.2)', 'rgba(255, 107, 107, 0.05)'],
        neutral: ['rgba(79, 195, 247, 0.2)', 'rgba(79, 195, 247, 0.05)'],
    },
    locale: 'fr',
    animationDuration: 800,
    responsive: true,
    maintainAspectRatio: true,
};

// ============================================================
// THEME MANAGEMENT
// ============================================================

class ThemeManager {
    constructor() {
        this.theme = 'dark';
        this.listeners = [];
        this.initializeTheme();
    }

    initializeTheme() {
        const saved = localStorage.getItem('nexus-theme');
        if (saved) {
            this.theme = saved;
        } else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
            this.theme = 'light';
        }
        this.applyTheme();
    }

    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
        document.querySelector('body')?.classList.toggle('dark-theme', this.theme === 'dark');
        document.querySelector('body')?.classList.toggle('light-theme', this.theme === 'light');
        this.notifyListeners();
    }

    toggleTheme() {
        this.theme = this.theme === 'dark' ? 'light' : 'dark';
        localStorage.setItem('nexus-theme', this.theme);
        this.applyTheme();
        return this.theme;
    }

    getTheme() {
        return this.theme;
    }

    getColors() {
        if (this.theme === 'dark') {
            return {
                ...CONFIG.colors,
                textColor: '#E0E0E0',
                gridColor: 'rgba(255, 255, 255, 0.06)',
                cardBg: 'rgba(26, 26, 46, 0.85)',
            };
        }
        return {
            ...CONFIG.colors,
            textColor: '#1A1A2E',
            gridColor: 'rgba(0, 0, 0, 0.08)',
            cardBg: 'rgba(255, 255, 255, 0.85)',
        };
    }

    addListener(callback) {
        this.listeners.push(callback);
    }

    notifyListeners() {
        const colors = this.getColors();
        this.listeners.forEach(cb => cb(colors));
    }
}

// ============================================================
// CHART FACTORY
// ============================================================

class ChartFactory {
    constructor() {
        this.charts = new Map();
        this.themeManager = new ThemeManager();
        this.defaultOptions = this.getDefaultOptions();
    }

    getDefaultOptions() {
        const colors = this.themeManager.getColors();
        return {
            responsive: CONFIG.responsive,
            maintainAspectRatio: CONFIG.maintainAspectRatio,
            animation: {
                duration: CONFIG.animationDuration,
                easing: 'easeInOutQuart',
            },
            plugins: {
                legend: {
                    labels: {
                        color: colors.textColor,
                        font: {
                            family: "'Inter', 'Segoe UI', sans-serif",
                            size: 12,
                            weight: '500',
                        },
                        padding: 20,
                        usePointStyle: true,
                        pointStyle: 'circle',
                    },
                },
                tooltip: {
                    backgroundColor: colors.cardBg,
                    titleColor: colors.textColor,
                    bodyColor: colors.textColor,
                    borderColor: colors.gridColor,
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 12,
                    boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                const value = context.parsed.y;
                                if (typeof value === 'number') {
                                    if (Math.abs(value) >= 1e6) {
                                        label += '$' + (value / 1e6).toFixed(2) + 'M';
                                    } else if (Math.abs(value) >= 1e3) {
                                        label += '$' + (value / 1e3).toFixed(2) + 'K';
                                    } else {
                                        label += '$' + value.toFixed(2);
                                    }
                                } else {
                                    label += value;
                                }
                            }
                            return label;
                        },
                        labelColor: function(context) {
                            return {
                                borderColor: context.dataset.borderColor,
                                backgroundColor: context.dataset.backgroundColor || context.dataset.borderColor,
                            };
                        },
                    },
                },
            },
            scales: {
                x: {
                    grid: {
                        color: colors.gridColor,
                        drawBorder: false,
                    },
                    ticks: {
                        color: colors.textColor,
                        font: {
                            family: "'Inter', 'Segoe UI', sans-serif",
                            size: 11,
                        },
                        maxTicksLimit: 15,
                    },
                },
                y: {
                    grid: {
                        color: colors.gridColor,
                        drawBorder: false,
                    },
                    ticks: {
                        color: colors.textColor,
                        font: {
                            family: "'Inter', 'Segoe UI', sans-serif",
                            size: 11,
                        },
                        callback: function(value) {
                            if (Math.abs(value) >= 1e6) {
                                return '$' + (value / 1e6).toFixed(1) + 'M';
                            }
                            if (Math.abs(value) >= 1e3) {
                                return '$' + (value / 1e3).toFixed(1) + 'K';
                            }
                            return '$' + value.toFixed(2);
                        },
                    },
                },
            },
            interaction: {
                intersect: false,
                mode: 'index',
                axis: 'x',
            },
        };
    }

    createChart(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            console.error(`Canvas element not found: ${canvasId}`);
            return null;
        }

        // Cleanup existing chart
        if (this.charts.has(canvasId)) {
            this.charts.get(canvasId).destroy();
            this.charts.delete(canvasId);
        }

        const ctx = canvas.getContext('2d');
        const chart = new Chart(ctx, this.mergeConfig(config));
        this.charts.set(canvasId, chart);

        // Add theme listener
        this.themeManager.addListener((colors) => {
            this.updateChartTheme(chart, colors);
        });

        return chart;
    }

    mergeConfig(config) {
        const colors = this.themeManager.getColors();
        return {
            ...this.defaultOptions,
            ...config,
            plugins: {
                ...this.defaultOptions.plugins,
                ...(config.plugins || {}),
                legend: {
                    ...this.defaultOptions.plugins.legend,
                    ...(config.plugins?.legend || {}),
                    labels: {
                        ...this.defaultOptions.plugins.legend.labels,
                        ...(config.plugins?.legend?.labels || {}),
                    },
                },
                tooltip: {
                    ...this.defaultOptions.plugins.tooltip,
                    ...(config.plugins?.tooltip || {}),
                },
            },
            scales: {
                ...this.defaultOptions.scales,
                ...(config.scales || {}),
                x: {
                    ...this.defaultOptions.scales.x,
                    ...(config.scales?.x || {}),
                },
                y: {
                    ...this.defaultOptions.scales.y,
                    ...(config.scales?.y || {}),
                },
            },
        };
    }

    updateChartTheme(chart, colors) {
        // Update global defaults
        Chart.defaults.color = colors.textColor;

        // Update scales
        if (chart.options.scales) {
            Object.keys(chart.options.scales).forEach(key => {
                const scale = chart.options.scales[key];
                if (scale.grid) {
                    scale.grid.color = colors.gridColor;
                }
                if (scale.ticks) {
                    scale.ticks.color = colors.textColor;
                }
            });
        }

        // Update legend
        if (chart.options.plugins?.legend?.labels) {
            chart.options.plugins.legend.labels.color = colors.textColor;
        }

        // Update tooltip
        if (chart.options.plugins?.tooltip) {
            chart.options.plugins.tooltip.backgroundColor = colors.cardBg;
            chart.options.plugins.tooltip.titleColor = colors.textColor;
            chart.options.plugins.tooltip.bodyColor = colors.textColor;
        }

        chart.update();
    }

    destroy(canvasId) {
        if (this.charts.has(canvasId)) {
            this.charts.get(canvasId).destroy();
            this.charts.delete(canvasId);
        }
    }

    destroyAll() {
        for (const [id, chart] of this.charts) {
            chart.destroy();
        }
        this.charts.clear();
    }
}

// ============================================================
// ARBITRAGE SPECIFIC CHARTS
// ============================================================

class ArbitrageCharts {
    constructor() {
        this.factory = new ChartFactory();
        this.charts = {};
        this.dataCache = new Map();
        this.updateInterval = null;
        this.websocket = null;
        this.isConnected = false;
    }

    // ==================== INITIALIZATION ====================

    initialize() {
        this.setupWebSocket();
        this.setupAutoUpdate();
        this.setupResizeHandler();
        this.setupThemeToggle();
        return this;
    }

    setupWebSocket() {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/arbitrage`;

        try {
            this.websocket = new WebSocket(wsUrl);
            this.websocket.onopen = () => this.onWebSocketOpen();
            this.websocket.onmessage = (event) => this.onWebSocketMessage(event);
            this.websocket.onclose = () => this.onWebSocketClose();
            this.websocket.onerror = (error) => this.onWebSocketError(error);
        } catch (error) {
            console.error('WebSocket connection failed:', error);
            this.fallbackToPolling();
        }
    }

    onWebSocketOpen() {
        this.isConnected = true;
        console.log('🔗 WebSocket connected to arbitrage data stream');
        this.updateConnectionStatus(true);
    }

    onWebSocketMessage(event) {
        try {
            const data = JSON.parse(event.data);
            this.handleRealtimeData(data);
        } catch (error) {
            console.error('WebSocket message parse error:', error);
        }
    }

    onWebSocketClose() {
        this.isConnected = false;
        console.warn('⚠️ WebSocket disconnected, switching to polling');
        this.updateConnectionStatus(false);
        this.fallbackToPolling();
    }

    onWebSocketError(error) {
        console.error('WebSocket error:', error);
    }

    handleRealtimeData(data) {
        const { type, payload } = data;

        switch (type) {
            case 'opportunity':
                this.updateOpportunityChart(payload);
                break;
            case 'execution':
                this.updateExecutionChart(payload);
                break;
            case 'pnl':
                this.updatePnLChart(payload);
                break;
            case 'spread':
                this.updateSpreadChart(payload);
                break;
            case 'volume':
                this.updateVolumeChart(payload);
                break;
            case 'arbitrage_matrix':
                this.updateArbitrageMatrix(payload);
                break;
            default:
                console.warn('Unknown data type:', type);
        }
    }

    updateConnectionStatus(isConnected) {
        const indicator = document.getElementById('connection-indicator');
        if (indicator) {
            indicator.className = isConnected ? 'connected' : 'disconnected';
            indicator.innerHTML = isConnected ? '🟢 Live' : '🔴 Offline';
        }
    }

    fallbackToPolling() {
        if (!this.updateInterval) {
            this.updateInterval = setInterval(() => {
                this.fetchData();
            }, 5000);
        }
    }

    setupAutoUpdate() {
        // Initial data fetch
        this.fetchData();

        // Set up periodic refresh (fallback)
        setInterval(() => {
            if (!this.isConnected) {
                this.fetchData();
            }
        }, 30000);
    }

    setupResizeHandler() {
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.resizeAllCharts();
            }, 250);
        });
    }

    setupThemeToggle() {
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => {
                this.factory.themeManager.toggleTheme();
            });
        }
    }

    // ==================== DATA FETCHING ====================

    async fetchData() {
        try {
            const endpoints = [
                '/api/arbitrage/opportunities',
                '/api/arbitrage/performance',
                '/api/arbitrage/spreads',
                '/api/arbitrage/volume',
                '/api/arbitrage/matrix',
            ];

            const responses = await Promise.all(
                endpoints.map(endpoint => fetch(endpoint).then(res => res.json()))
            );

            const [opportunities, performance, spreads, volume, matrix] = responses;

            this.updateOpportunityChart(opportunities);
            this.updateExecutionChart(performance);
            this.updatePnLChart(performance);
            this.updateSpreadChart(spreads);
            this.updateVolumeChart(volume);
            this.updateArbitrageMatrix(matrix);
        } catch (error) {
            console.error('Data fetch error:', error);
        }
    }

    // ==================== OPPORTUNITY CHART ====================

    createOpportunityChart() {
        const config = {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Arbitrage Opportunities',
                    data: [],
                    backgroundColor: (context) => {
                        const value = context.parsed?.y || 0;
                        return value >= 0 ? CONFIG.colors.success : CONFIG.colors.danger;
                    },
                    borderColor: (context) => {
                        const value = context.parsed?.y || 0;
                        return value >= 0 ? CONFIG.colors.success : CONFIG.colors.danger;
                    },
                    borderWidth: 1,
                    pointRadius: 4,
                    pointHoverRadius: 8,
                    pointHoverBorderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: '📊 Arbitrage Opportunities',
                        font: {
                            size: 16,
                            weight: 'bold',
                        },
                        color: this.factory.themeManager.getColors().textColor,
                        padding: 20,
                    },
                    subtitle: {
                        display: true,
                        text: 'Real-time arbitrage spread detection',
                        font: {
                            size: 12,
                        },
                        color: this.factory.themeManager.getColors().textColor,
                        padding: { bottom: 15 },
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const point = context.raw;
                                return [
                                    `Pair: ${point.pair || 'N/A'}`,
                                    `Spread: $${point.y?.toFixed(2) || 'N/A'}`,
                                    `Exchange A: ${point.exchangeA || 'N/A'}`,
                                    `Exchange B: ${point.exchangeB || 'N/A'}`,
                                    `Profit: ${point.profit ? '$' + point.profit.toFixed(2) : 'N/A'}`,
                                ];
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute',
                            displayFormats: {
                                minute: 'HH:mm',
                            },
                        },
                        title: {
                            display: true,
                            text: 'Time',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Spread (USD)',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                        beginAtZero: true,
                    },
                },
            },
        };

        this.charts.opportunity = this.factory.createChart('opportunityChart', config);
        return this.charts.opportunity;
    }

    updateOpportunityChart(data) {
        if (!this.charts.opportunity) {
            this.createOpportunityChart();
        }

        const chart = this.charts.opportunity;
        const dataset = chart.data.datasets[0];

        // Format data for scatter plot
        const formattedData = data.map(item => ({
            x: new Date(item.timestamp),
            y: item.spread || item.priceDiff || 0,
            pair: item.pair,
            exchangeA: item.exchangeA,
            exchangeB: item.exchangeB,
            profit: item.estimatedProfit,
            volume: item.volume,
        }));

        dataset.data = formattedData;
        dataset.pointBackgroundColor = formattedData.map(d => d.y >= 0 ? CONFIG.colors.success : CONFIG.colors.danger);

        chart.update('none');
    }

    // ==================== EXECUTION CHART ====================

    createExecutionChart() {
        const config = {
            type: 'line',
            data: {
                datasets: [
                    {
                        label: 'Arbitrage Trades',
                        data: [],
                        borderColor: CONFIG.colors.primary,
                        backgroundColor: (context) => {
                            const chart = context.chart;
                            const { ctx, chartArea } = chart;
                            if (!chartArea) return 'rgba(0, 212, 170, 0.1)';
                            const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                            gradient.addColorStop(0, 'rgba(0, 212, 170, 0.4)');
                            gradient.addColorStop(1, 'rgba(0, 212, 170, 0.05)');
                            return gradient;
                        },
                        borderWidth: 2,
                        pointRadius: 3,
                        pointHoverRadius: 6,
                        tension: 0.3,
                        fill: true,
                    },
                    {
                        label: 'Cumulative PnL',
                        data: [],
                        borderColor: CONFIG.colors.warning,
                        backgroundColor: 'rgba(255, 183, 77, 0.1)',
                        borderWidth: 2,
                        pointRadius: 0,
                        borderDash: [5, 5],
                        tension: 0.3,
                        fill: true,
                        yAxisID: 'y1',
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
                plugins: {
                    title: {
                        display: true,
                        text: '⚡ Execution Performance',
                        font: {
                            size: 16,
                            weight: 'bold',
                        },
                        color: this.factory.themeManager.getColors().textColor,
                        padding: 20,
                    },
                    subtitle: {
                        display: true,
                        text: 'Trades executed and cumulative P&L',
                        font: {
                            size: 12,
                        },
                        color: this.factory.themeManager.getColors().textColor,
                        padding: { bottom: 15 },
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.dataset.label || '';
                                const value = context.parsed.y;
                                if (context.dataset.yAxisID === 'y1') {
                                    return `${label}: $${value.toFixed(2)}`;
                                }
                                return `${label}: ${value}`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute',
                            displayFormats: {
                                minute: 'HH:mm',
                            },
                        },
                        title: {
                            display: true,
                            text: 'Time',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Trade Count',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                        beginAtZero: true,
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Cumulative PnL (USD)',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    },
                },
            },
        };

        this.charts.execution = this.factory.createChart('executionChart', config);
        return this.charts.execution;
    }

    updateExecutionChart(data) {
        if (!this.charts.execution) {
            this.createExecutionChart();
        }

        const chart = this.charts.execution;
        const trades = data.trades || data.executions || [];

        // Format execution data
        const tradeData = trades.map(t => ({
            x: new Date(t.timestamp),
            y: t.count || 1,
        }));

        // Calculate cumulative PnL
        let cumulative = 0;
        const cumulativeData = trades.map(t => {
            cumulative += t.pnl || t.profit || 0;
            return {
                x: new Date(t.timestamp),
                y: cumulative,
            };
        });

        chart.data.datasets[0].data = tradeData;
        chart.data.datasets[1].data = cumulativeData;

        chart.update('none');
    }

    // ==================== PNL CHART ====================

    createPnLChart() {
        const config = {
            type: 'line',
            data: {
                datasets: [
                    {
                        label: 'Realized PnL',
                        data: [],
                        borderColor: CONFIG.colors.success,
                        backgroundColor: (context) => {
                            const chart = context.chart;
                            const { ctx, chartArea } = chart;
                            if (!chartArea) return 'rgba(0, 212, 170, 0.1)';
                            const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                            gradient.addColorStop(0, 'rgba(0, 212, 170, 0.3)');
                            gradient.addColorStop(1, 'rgba(0, 212, 170, 0.03)');
                            return gradient;
                        },
                        borderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        tension: 0.4,
                        fill: true,
                    },
                    {
                        label: 'Unrealized PnL',
                        data: [],
                        borderColor: CONFIG.colors.info,
                        backgroundColor: (context) => {
                            const chart = context.chart;
                            const { ctx, chartArea } = chart;
                            if (!chartArea) return 'rgba(79, 195, 247, 0.1)';
                            const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                            gradient.addColorStop(0, 'rgba(79, 195, 247, 0.3)');
                            gradient.addColorStop(1, 'rgba(79, 195, 247, 0.03)');
                            return gradient;
                        },
                        borderWidth: 2,
                        pointRadius: 3,
                        pointHoverRadius: 6,
                        tension: 0.4,
                        fill: true,
                        borderDash: [4, 4],
                    },
                    {
                        label: 'Total PnL',
                        data: [],
                        borderColor: CONFIG.colors.warning,
                        backgroundColor: 'transparent',
                        borderWidth: 3,
                        pointRadius: 0,
                        tension: 0.4,
                        pointHoverRadius: 5,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: '💰 Profit & Loss Evolution',
                        font: {
                            size: 16,
                            weight: 'bold',
                        },
                        color: this.factory.themeManager.getColors().textColor,
                        padding: 20,
                    },
                    subtitle: {
                        display: true,
                        text: 'Real-time P&L tracking across all arbitrage operations',
                        font: {
                            size: 12,
                        },
                        color: this.factory.themeManager.getColors().textColor,
                        padding: { bottom: 15 },
                    },
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute',
                            displayFormats: {
                                minute: 'HH:mm',
                            },
                        },
                        title: {
                            display: true,
                            text: 'Time',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'PnL (USD)',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                    },
                },
            },
        };

        this.charts.pnl = this.factory.createChart('pnlChart', config);
        return this.charts.pnl;
    }

    updatePnLChart(data) {
        if (!this.charts.pnl) {
            this.createPnLChart();
        }

        const chart = this.charts.pnl;
        const history = data.history || data.pnlHistory || [];

        const realizedData = history.map(h => ({
            x: new Date(h.timestamp),
            y: h.realized || 0,
        }));

        const unrealizedData = history.map(h => ({
            x: new Date(h.timestamp),
            y: h.unrealized || 0,
        }));

        const totalData = history.map(h => ({
            x: new Date(h.timestamp),
            y: (h.realized || 0) + (h.unrealized || 0),
        }));

        chart.data.datasets[0].data = realizedData;
        chart.data.datasets[1].data = unrealizedData;
        chart.data.datasets[2].data = totalData;

        chart.update('none');
    }

    // ==================== SPREAD CHART ====================

    createSpreadChart() {
        const config = {
            type: 'line',
            data: {
                datasets: [
                    {
                        label: 'Exchange A Price',
                        data: [],
                        borderColor: CONFIG.colors.primary,
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        pointRadius: 1,
                        tension: 0.2,
                    },
                    {
                        label: 'Exchange B Price',
                        data: [],
                        borderColor: CONFIG.colors.warning,
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        pointRadius: 1,
                        tension: 0.2,
                    },
                    {
                        label: 'Spread (Diff)',
                        data: [],
                        borderColor: CONFIG.colors.danger,
                        backgroundColor: (context) => {
                            const chart = context.chart;
                            const { ctx, chartArea } = chart;
                            if (!chartArea) return 'rgba(255, 107, 107, 0.05)';
                            const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                            gradient.addColorStop(0, 'rgba(255, 107, 107, 0.2)');
                            gradient.addColorStop(1, 'rgba(255, 107, 107, 0.02)');
                            return gradient;
                        },
                        borderWidth: 2,
                        pointRadius: 2,
                        tension: 0.2,
                        fill: true,
                        yAxisID: 'y1',
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: '📈 Price Spread Analysis',
                        font: {
                            size: 16,
                            weight: 'bold',
                        },
                        color: this.factory.themeManager.getColors().textColor,
                        padding: 20,
                    },
                    subtitle: {
                        display: true,
                        text: 'Real-time price comparison between exchanges',
                        font: {
                            size: 12,
                        },
                        color: this.factory.themeManager.getColors().textColor,
                        padding: { bottom: 15 },
                    },
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute',
                            displayFormats: {
                                minute: 'HH:mm',
                            },
                        },
                        title: {
                            display: true,
                            text: 'Time',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Price (USD)',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                    },
                    y1: {
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Spread (USD)',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    },
                },
            },
        };

        this.charts.spread = this.factory.createChart('spreadChart', config);
        return this.charts.spread;
    }

    updateSpreadChart(data) {
        if (!this.charts.spread) {
            this.createSpreadChart();
        }

        const chart = this.charts.spread;
        const pairData = data.pairData || data;

        // Extract price data
        const exchangeAPrices = pairData.map(p => ({
            x: new Date(p.timestamp),
            y: p.priceA || p.exchangeAPrice || 0,
        }));

        const exchangeBPrices = pairData.map(p => ({
            x: new Date(p.timestamp),
            y: p.priceB || p.exchangeBPrice || 0,
        }));

        const spreads = pairData.map(p => ({
            x: new Date(p.timestamp),
            y: Math.abs((p.priceA || 0) - (p.priceB || 0)),
        }));

        chart.data.datasets[0].data = exchangeAPrices;
        chart.data.datasets[1].data = exchangeBPrices;
        chart.data.datasets[2].data = spreads;

        chart.update('none');
    }

    // ==================== VOLUME CHART ====================

    createVolumeChart() {
        const config = {
            type: 'bar',
            data: {
                datasets: [
                    {
                        label: 'Exchange A Volume',
                        data: [],
                        backgroundColor: 'rgba(0, 212, 170, 0.6)',
                        borderColor: CONFIG.colors.success,
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                    {
                        label: 'Exchange B Volume',
                        data: [],
                        backgroundColor: 'rgba(255, 183, 77, 0.6)',
                        borderColor: CONFIG.colors.warning,
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                    {
                        label: 'Arbitrage Volume',
                        data: [],
                        backgroundColor: 'rgba(255, 107, 107, 0.6)',
                        borderColor: CONFIG.colors.danger,
                        borderWidth: 1,
                        borderRadius: 4,
                        yAxisID: 'y1',
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: '📊 Trading Volume Analysis',
                        font: {
                            size: 16,
                            weight: 'bold',
                        },
                        color: this.factory.themeManager.getColors().textColor,
                        padding: 20,
                    },
                    subtitle: {
                        display: true,
                        text: 'Volume comparison across exchanges and arbitrage activity',
                        font: {
                            size: 12,
                        },
                        color: this.factory.themeManager.getColors().textColor,
                        padding: { bottom: 15 },
                    },
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'minute',
                            displayFormats: {
                                minute: 'HH:mm',
                            },
                        },
                        title: {
                            display: true,
                            text: 'Time',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Volume (Units)',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                        beginAtZero: true,
                    },
                    y1: {
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Arbitrage Volume',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                        beginAtZero: true,
                    },
                },
            },
        };

        this.charts.volume = this.factory.createChart('volumeChart', config);
        return this.charts.volume;
    }

    updateVolumeChart(data) {
        if (!this.charts.volume) {
            this.createVolumeChart();
        }

        const chart = this.charts.volume;
        const volumeData = data.volumes || data;

        const exchangeAVol = volumeData.map(v => ({
            x: new Date(v.timestamp),
            y: v.exchangeAVolume || 0,
        }));

        const exchangeBVol = volumeData.map(v => ({
            x: new Date(v.timestamp),
            y: v.exchangeBVolume || 0,
        }));

        const arbitrageVol = volumeData.map(v => ({
            x: new Date(v.timestamp),
            y: v.arbitrageVolume || 0,
        }));

        chart.data.datasets[0].data = exchangeAVol;
        chart.data.datasets[1].data = exchangeBVol;
        chart.data.datasets[2].data = arbitrageVol;

        chart.update('none');
    }

    // ==================== ARBITRAGE MATRIX ====================

    createArbitrageMatrix() {
        // Use a custom canvas or table-based visualization
        const container = document.getElementById('arbitrageMatrix');
        if (!container) return;

        // Create a canvas for the matrix heatmap
        const canvas = document.createElement('canvas');
        canvas.id = 'matrixCanvas';
        canvas.width = container.clientWidth || 600;
        canvas.height = container.clientHeight || 400;
        container.appendChild(canvas);

        const config = {
            type: 'matrix',
            data: {
                datasets: [{
                    label: 'Arbitrage Matrix',
                    data: [],
                    backgroundColor: (context) => {
                        const value = context.raw.v;
                        if (value > 1) return '#00D4AA';
                        if (value > 0.5) return '#4FC3F7';
                        if (value > 0) return '#FFB74D';
                        return '#FF6B6B';
                    },
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    width: (context) => {
                        const chart = context.chart;
                        const xAxis = chart.scales.x;
                        return xAxis.getPixelForTick(1) - xAxis.getPixelForTick(0);
                    },
                    height: (context) => {
                        const chart = context.chart;
                        const yAxis = chart.scales.y;
                        return yAxis.getPixelForTick(1) - yAxis.getPixelForTick(0);
                    },
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: '🔗 Arbitrage Matrix Heatmap',
                        font: {
                            size: 16,
                            weight: 'bold',
                        },
                        color: this.factory.themeManager.getColors().textColor,
                        padding: 20,
                    },
                    subtitle: {
                        display: true,
                        text: 'Cross-exchange arbitrage opportunities matrix',
                        font: {
                            size: 12,
                        },
                        color: this.factory.themeManager.getColors().textColor,
                        padding: { bottom: 15 },
                    },
                    legend: {
                        display: false,
                    },
                    tooltip: {
                        callbacks: {
                            title: function(context) {
                                return `${context[0].raw.x} → ${context[0].raw.y}`;
                            },
                            label: function(context) {
                                const data = context.raw;
                                return [
                                    `Spread: $${data.v?.toFixed(2) || 'N/A'}`,
                                    `Profit: $${data.profit?.toFixed(2) || 'N/A'}`,
                                    `Volume: ${data.volume || 'N/A'}`,
                                ];
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        type: 'category',
                        labels: [],
                        title: {
                            display: true,
                            text: 'From Exchange',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                    },
                    y: {
                        type: 'category',
                        labels: [],
                        title: {
                            display: true,
                            text: 'To Exchange',
                            color: this.factory.themeManager.getColors().textColor,
                        },
                        reverse: true,
                    },
                },
            },
        };

        this.charts.matrix = this.factory.createChart('matrixCanvas', config);
        return this.charts.matrix;
    }

    updateArbitrageMatrix(data) {
        if (!this.charts.matrix) {
            this.createArbitrageMatrix();
        }

        const chart = this.charts.matrix;
        const matrixData = data.matrix || data;

        // Extract exchange names
        const exchanges = Object.keys(matrixData);
        const labels = exchanges;

        // Flatten matrix data for matrix chart
        const flattenedData = [];
        exchanges.forEach((from, i) => {
            exchanges.forEach((to, j) => {
                const value = matrixData[from]?.[to] || 0;
                flattenedData.push({
                    x: from,
                    y: to,
                    v: value,
                    profit: matrixData[from]?.[to]?.profit || 0,
                    volume: matrixData[from]?.[to]?.volume || 0,
                });
            });
        });

        chart.data.datasets[0].data = flattenedData;
        chart.data.labels = labels;

        chart.update('none');
    }

    // ==================== UTILITY METHODS ====================

    resizeAllCharts() {
        for (const [id, chart] of this.factory.charts) {
            chart.resize();
        }
    }

    destroyAll() {
        this.factory.destroyAll();
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
        this.charts = {};
    }
}

// ============================================================
// INITIALIZATION
// ============================================================

let arbitrageCharts = null;

function initializeCharts() {
    if (arbitrageCharts) {
        arbitrageCharts.destroyAll();
    }
    arbitrageCharts = new ArbitrageCharts();
    arbitrageCharts.initialize();

    // Create all charts
    arbitrageCharts.createOpportunityChart();
    arbitrageCharts.createExecutionChart();
    arbitrageCharts.createPnLChart();
    arbitrageCharts.createSpreadChart();
    arbitrageCharts.createVolumeChart();
    arbitrageCharts.createArbitrageMatrix();

    console.log('📊 Nexus Arbitrage Charts initialized successfully');
}

// ============================================================
// EXPORTS
// ============================================================

export {
    ArbitrageCharts,
    ChartFactory,
    ThemeManager,
    CONFIG,
    initializeCharts,
    arbitrageCharts,
};

// ============================================================
// AUTO-INITIALIZATION
// ============================================================

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeCharts);
} else {
    initializeCharts();
}

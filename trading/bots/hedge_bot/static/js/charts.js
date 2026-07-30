/**
 * trading/bots/hedge_bot/static/js/charts.js
 * NEXUS AI TRADING SYSTEM - Hedge Bot Charting Library
 * Version: 2.0.0
 * Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
 */

/**
 * NEXUS Chart Library
 * 
 * A comprehensive charting library for the NEXUS Hedge Bot dashboard.
 * Features include:
 * - Candlestick charts
 * - Line charts
 * - Bar charts
 * - Area charts
 * - Pie charts
 * - Donut charts
 * - Heatmap charts
 * - Correlation matrix
 * - Multiple chart types
 * - Real-time updates
 * - Customizable themes
 * - Interactive tooltips
 * - Zoom and pan
 * - Export capabilities
 * - Responsive design
 */

class NexusChart {
    /**
     * Create a new chart instance
     * 
     * @param {string|HTMLElement} container - Chart container selector or element
     * @param {Object} options - Chart options
     * @param {string} options.type - Chart type (candlestick, line, bar, area, pie, donut, heatmap, correlation)
     * @param {Object} options.data - Chart data
     * @param {Object} options.theme - Chart theme
     * @param {Object} options.options - Chart configuration options
     */
    constructor(container, options = {}) {
        // Container
        this.container = typeof container === 'string' 
            ? document.querySelector(container) 
            : container;

        if (!this.container) {
            throw new Error('Chart container not found');
        }

        // Configuration
        this.config = {
            type: options.type || 'line',
            data: options.data || { labels: [], datasets: [] },
            theme: options.theme || this._getDefaultTheme(),
            options: options.options || {},
            responsive: options.responsive !== undefined ? options.responsive : true,
            maintainAspectRatio: options.maintainAspectRatio !== undefined ? options.maintainAspectRatio : true,
            animation: options.animation !== undefined ? options.animation : true,
            plugins: options.plugins || [],
        };

        // State
        this.chart = null;
        this.isRendered = false;
        this.resizeObserver = null;
        this.updateQueue = [];
        this.isUpdating = false;

        // Initialize
        this._init();

        this.log('Chart initialized:', this.config.type);
    }

    // ============================================================
    // INITIALIZATION
    // ============================================================

    /**
     * Initialize chart
     */
    _init() {
        // Validate data
        this._validateData();

        // Create canvas if needed
        this._createCanvas();

        // Apply theme
        this._applyTheme();

        // Render chart
        this.render();

        // Setup resize observer
        this._setupResizeObserver();

        // Setup event handlers
        this._setupEventHandlers();
    }

    /**
     * Validate chart data
     */
    _validateData() {
        const data = this.config.data;
        if (!data.datasets || !data.datasets.length) {
            throw new Error('Chart data must contain at least one dataset');
        }
    }

    /**
     * Create canvas element
     */
    _createCanvas() {
        // Check if canvas already exists
        let canvas = this.container.querySelector('canvas');
        if (!canvas) {
            canvas = document.createElement('canvas');
            this.container.appendChild(canvas);
        }
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
    }

    /**
     * Apply theme
     */
    _applyTheme() {
        const theme = this.config.theme;
        if (!theme) return;

        // Apply theme to container
        if (theme.backgroundColor) {
            this.container.style.backgroundColor = theme.backgroundColor;
        }
        if (theme.color) {
            this.container.style.color = theme.color;
        }

        // Apply theme to canvas
        if (this.canvas) {
            // Theme will be applied during render
        }
    }

    // ============================================================
    // RENDERING
    // ============================================================

    /**
     * Render chart
     * 
     * @param {Object} options - Render options
     * @returns {Promise<void>}
     */
    async render(options = {}) {
        if (this.isRendered && !options.force) {
            this.log('Chart already rendered, use update() to update');
            return;
        }

        this.log('Rendering chart:', this.config.type);

        // Set canvas size
        this._resizeCanvas();

        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Render based on type
        switch (this.config.type) {
            case 'candlestick':
                this._renderCandlestick();
                break;
            case 'line':
                this._renderLine();
                break;
            case 'bar':
                this._renderBar();
                break;
            case 'area':
                this._renderArea();
                break;
            case 'pie':
                this._renderPie();
                break;
            case 'donut':
                this._renderDonut();
                break;
            case 'heatmap':
                this._renderHeatmap();
                break;
            case 'correlation':
                this._renderCorrelation();
                break;
            default:
                throw new Error(`Unsupported chart type: ${this.config.type}`);
        }

        this.isRendered = true;
        this._emit('render', { chart: this });
    }

    /**
     * Update chart with new data
     * 
     * @param {Object} data - New chart data
     * @param {Object} options - Update options
     * @returns {Promise<void>}
     */
    async update(data = null, options = {}) {
        if (data) {
            this.config.data = data;
        }

        if (this.isUpdating) {
            this.updateQueue.push({ data, options });
            return;
        }

        this.isUpdating = true;

        try {
            this.log('Updating chart');

            // Clear canvas
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

            // Re-render
            await this.render({ force: true, ...options });

            this._emit('update', { chart: this, data: this.config.data });

        } catch (error) {
            this.log('Update error:', error);
            throw error;
        } finally {
            this.isUpdating = false;
            if (this.updateQueue.length) {
                const next = this.updateQueue.shift();
                this.update(next.data, next.options);
            }
        }
    }

    /**
     * Resize canvas
     */
    _resizeCanvas() {
        const rect = this.container.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;

        // Set canvas size
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;

        // Set CSS size
        this.canvas.style.width = `${rect.width}px`;
        this.canvas.style.height = `${rect.height}px`;

        // Scale context
        this.ctx.scale(dpr, dpr);

        // Store dimensions
        this.width = rect.width;
        this.height = rect.height;
        this.dpr = dpr;
    }

    // ============================================================
    // CHART TYPES
    // ============================================================

    /**
     * Render candlestick chart
     */
    _renderCandlestick() {
        const data = this.config.data;
        const dataset = data.datasets[0];
        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        const padding = { top: 20, right: 20, bottom: 30, left: 50 };

        // Calculate ranges
        const prices = dataset.data.flatMap(d => [d.high, d.low, d.open, d.close]);
        const max = Math.max(...prices);
        const min = Math.min(...prices);
        const range = max - min;

        const chartW = w - padding.left - padding.right;
        const chartH = h - padding.top - padding.bottom;
        const candleW = Math.min(chartW / dataset.data.length * 0.8, 10);

        // Draw axes
        this._drawAxes(ctx, padding, w, h, min, max);

        // Draw candles
        dataset.data.forEach((candle, i) => {
            const x = padding.left + (i / dataset.data.length) * chartW;
            const highY = padding.top + chartH - ((candle.high - min) / range) * chartH;
            const lowY = padding.top + chartH - ((candle.low - min) / range) * chartH;
            const openY = padding.top + chartH - ((candle.open - min) / range) * chartH;
            const closeY = padding.top + chartH - ((candle.close - min) / range) * chartH;

            const color = candle.close >= candle.open 
                ? this.config.theme.positiveColor || '#00ff88'
                : this.config.theme.negativeColor || '#ff4444';

            // Draw wick
            ctx.beginPath();
            ctx.moveTo(x, highY);
            ctx.lineTo(x, lowY);
            ctx.strokeStyle = color;
            ctx.lineWidth = 1;
            ctx.stroke();

            // Draw body
            const bodyTop = Math.min(openY, closeY);
            const bodyBottom = Math.max(openY, closeY);
            const bodyH = Math.max(bodyBottom - bodyTop, 1);

            ctx.fillStyle = color;
            ctx.fillRect(x - candleW / 2, bodyTop, candleW, bodyH);

            // Draw border
            ctx.strokeStyle = color;
            ctx.lineWidth = 0.5;
            ctx.strokeRect(x - candleW / 2, bodyTop, candleW, bodyH);
        });

        // Draw legend
        if (dataset.label) {
            this._drawLegend(ctx, dataset.label, padding);
        }

        // Draw grid
        this._drawGrid(ctx, padding, w, h, min, max);
    }

    /**
     * Render line chart
     */
    _renderLine() {
        const data = this.config.data;
        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        const padding = { top: 20, right: 20, bottom: 30, left: 50 };

        // Calculate ranges
        const allValues = data.datasets.flatMap(d => d.data);
        const max = Math.max(...allValues);
        const min = Math.min(...allValues);
        const range = max - min || 1;

        const chartW = w - padding.left - padding.right;
        const chartH = h - padding.top - padding.bottom;

        // Draw axes
        this._drawAxes(ctx, padding, w, h, min, max);

        // Draw grid
        this._drawGrid(ctx, padding, w, h, min, max);

        // Draw datasets
        data.datasets.forEach((dataset, idx) => {
            const color = dataset.color || this._getColor(idx);

            // Draw area if dataset has fill
            if (dataset.fill) {
                ctx.beginPath();
                const firstX = padding.left + (0 / dataset.data.length) * chartW;
                const firstY = padding.top + chartH - ((dataset.data[0] - min) / range) * chartH;
                ctx.moveTo(firstX, padding.top + chartH);
                ctx.lineTo(firstX, firstY);

                dataset.data.forEach((value, i) => {
                    const x = padding.left + (i / dataset.data.length) * chartW;
                    const y = padding.top + chartH - ((value - min) / range) * chartH;
                    ctx.lineTo(x, y);
                });

                const lastX = padding.left + ((dataset.data.length - 1) / dataset.data.length) * chartW;
                ctx.lineTo(lastX, padding.top + chartH);
                ctx.closePath();
                ctx.fillStyle = color + '33';
                ctx.fill();
            }

            // Draw line
            ctx.beginPath();
            dataset.data.forEach((value, i) => {
                const x = padding.left + (i / dataset.data.length) * chartW;
                const y = padding.top + chartH - ((value - min) / range) * chartH;
                if (i === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            });
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.stroke();

            // Draw points
            if (dataset.points !== false) {
                dataset.data.forEach((value, i) => {
                    const x = padding.left + (i / dataset.data.length) * chartW;
                    const y = padding.top + chartH - ((value - min) / range) * chartH;
                    ctx.beginPath();
                    ctx.arc(x, y, 4, 0, Math.PI * 2);
                    ctx.fillStyle = color;
                    ctx.fill();
                    ctx.strokeStyle = this.config.theme.backgroundColor || '#fff';
                    ctx.lineWidth = 1;
                    ctx.stroke();
                });
            }

            // Draw label
            if (dataset.label) {
                this._drawLegend(ctx, dataset.label, padding, idx);
            }
        });

        // Draw x-axis labels
        if (data.labels) {
            data.labels.forEach((label, i) => {
                const x = padding.left + (i / data.labels.length) * chartW;
                ctx.fillStyle = this.config.theme.textColor || '#9ca3af';
                ctx.font = '12px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(label, x, h - 5);
            });
        }
    }

    /**
     * Render bar chart
     */
    _renderBar() {
        const data = this.config.data;
        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        const padding = { top: 20, right: 20, bottom: 30, left: 50 };

        const allValues = data.datasets.flatMap(d => d.data);
        const max = Math.max(...allValues);
        const min = Math.min(...allValues, 0);
        const range = max - min || 1;

        const chartW = w - padding.left - padding.right;
        const chartH = h - padding.top - padding.bottom;
        const barGroupW = chartW / data.datasets[0].data.length;
        const barW = Math.min(barGroupW / data.datasets.length * 0.8, 30);

        // Draw axes
        this._drawAxes(ctx, padding, w, h, min, max);

        // Draw grid
        this._drawGrid(ctx, padding, w, h, min, max);

        // Draw datasets
        data.datasets.forEach((dataset, idx) => {
            const color = dataset.color || this._getColor(idx);
            const offset = (idx - (data.datasets.length - 1) / 2) * barW;

            dataset.data.forEach((value, i) => {
                const x = padding.left + (i / dataset.data.length) * chartW + offset + barW / 2;
                const barH = (value / range) * chartH;
                const y = value >= 0 
                    ? padding.top + chartH - barH
                    : padding.top + chartH;

                ctx.fillStyle = color;
                ctx.fillRect(x - barW / 2, y, barW, Math.abs(barH));

                // Draw value on top of bar
                if (dataset.showValues !== false) {
                    ctx.fillStyle = this.config.theme.textColor || '#9ca3af';
                    ctx.font = '10px sans-serif';
                    ctx.textAlign = 'center';
                    ctx.fillText(
                        value.toFixed(2),
                        x,
                        value >= 0 ? y - 5 : y + 15
                    );
                }
            });

            // Draw label
            if (dataset.label) {
                this._drawLegend(ctx, dataset.label, padding, idx);
            }
        });

        // Draw x-axis labels
        if (data.labels) {
            data.labels.forEach((label, i) => {
                const x = padding.left + (i / data.labels.length) * chartW + barGroupW / 2;
                ctx.fillStyle = this.config.theme.textColor || '#9ca3af';
                ctx.font = '12px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(label, x, h - 5);
            });
        }
    }

    /**
     * Render area chart
     */
    _renderArea() {
        // Area chart is similar to line chart with fill
        this.config.data.datasets.forEach(d => d.fill = true);
        this._renderLine();
    }

    /**
     * Render pie chart
     */
    _renderPie() {
        const data = this.config.data;
        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        const centerX = w / 2;
        const centerY = h / 2;
        const radius = Math.min(w, h) / 2 - 40;

        const total = data.datasets[0].data.reduce((a, b) => a + b, 0);
        let startAngle = -Math.PI / 2;

        data.datasets[0].data.forEach((value, i) => {
            const sliceAngle = (value / total) * 2 * Math.PI;
            const color = this._getColor(i);

            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.arc(centerX, centerY, radius, startAngle, startAngle + sliceAngle);
            ctx.closePath();

            ctx.fillStyle = color;
            ctx.fill();

            ctx.strokeStyle = this.config.theme.backgroundColor || '#fff';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Draw label
            const midAngle = startAngle + sliceAngle / 2;
            const labelRadius = radius * 0.65;
            const labelX = centerX + Math.cos(midAngle) * labelRadius;
            const labelY = centerY + Math.sin(midAngle) * labelRadius;

            const percentage = ((value / total) * 100);
            if (percentage > 5) {
                ctx.fillStyle = '#fff';
                ctx.font = 'bold 12px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(`${percentage.toFixed(1)}%`, labelX, labelY);
            }

            startAngle += sliceAngle;
        });

        // Draw center text
        if (data.datasets[0].label) {
            ctx.fillStyle = this.config.theme.textColor || '#9ca3af';
            ctx.font = '16px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(data.datasets[0].label, centerX, centerY + 20);
        }

        // Draw legend
        this._drawLegend(ctx, null, { top: 20, right: 20, bottom: 20, left: 20 });
    }

    /**
     * Render donut chart
     */
    _renderDonut() {
        const data = this.config.data;
        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        const centerX = w / 2;
        const centerY = h / 2;
        const outerRadius = Math.min(w, h) / 2 - 40;
        const innerRadius = outerRadius * 0.6;

        const total = data.datasets[0].data.reduce((a, b) => a + b, 0);
        let startAngle = -Math.PI / 2;

        data.datasets[0].data.forEach((value, i) => {
            const sliceAngle = (value / total) * 2 * Math.PI;
            const color = this._getColor(i);

            ctx.beginPath();
            ctx.arc(centerX, centerY, outerRadius, startAngle, startAngle + sliceAngle);
            ctx.arc(centerX, centerY, innerRadius, startAngle + sliceAngle, startAngle, true);
            ctx.closePath();

            ctx.fillStyle = color;
            ctx.fill();

            ctx.strokeStyle = this.config.theme.backgroundColor || '#fff';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Draw label
            const midAngle = startAngle + sliceAngle / 2;
            const labelRadius = (outerRadius + innerRadius) / 2;
            const labelX = centerX + Math.cos(midAngle) * labelRadius;
            const labelY = centerY + Math.sin(midAngle) * labelRadius;

            const percentage = ((value / total) * 100);
            if (percentage > 5) {
                ctx.fillStyle = '#fff';
                ctx.font = 'bold 10px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(`${percentage.toFixed(1)}%`, labelX, labelY);
            }

            startAngle += sliceAngle;
        });

        // Draw center text
        ctx.fillStyle = this.config.theme.textColor || '#9ca3af';
        ctx.font = '24px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Total', centerX, centerY - 10);
        ctx.font = '18px sans-serif';
        ctx.fillStyle = this.config.theme.textColor || '#e5e7eb';
        ctx.fillText(total.toLocaleString(), centerX, centerY + 20);

        // Draw legend
        this._drawLegend(ctx, null, { top: 20, right: 20, bottom: 20, left: 20 });
    }

    /**
     * Render heatmap chart
     */
    _renderHeatmap() {
        const data = this.config.data;
        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        const padding = { top: 40, right: 40, bottom: 40, left: 40 };

        const matrix = data.datasets[0].data;
        const rows = matrix.length;
        const cols = matrix[0].length;

        const chartW = w - padding.left - padding.right;
        const chartH = h - padding.top - padding.bottom;
        const cellW = chartW / cols;
        const cellH = chartH / rows;

        const allValues = matrix.flat();
        const max = Math.max(...allValues);
        const min = Math.min(...allValues);
        const range = max - min || 1;

        // Draw heatmap
        matrix.forEach((row, i) => {
            row.forEach((value, j) => {
                const x = padding.left + j * cellW;
                const y = padding.top + i * cellH;
                const normalized = (value - min) / range;

                // Color gradient from blue to red
                const r = Math.round(normalized * 255);
                const b = Math.round((1 - normalized) * 255);
                const g = Math.round(128 - Math.abs(normalized - 0.5) * 128);

                ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
                ctx.fillRect(x, y, cellW, cellH);

                // Draw value
                ctx.fillStyle = normalized > 0.5 ? '#fff' : '#000';
                ctx.font = '10px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(value.toFixed(2), x + cellW / 2, y + cellH / 2);
            });
        });

        // Draw labels
        if (data.labels) {
            data.labels.forEach((label, i) => {
                // X-axis labels
                ctx.fillStyle = this.config.theme.textColor || '#9ca3af';
                ctx.font = '10px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillText(label, padding.left + i * cellW + cellW / 2, h - padding.bottom + 5);
            });
        }

        if (data.rowLabels) {
            data.rowLabels.forEach((label, i) => {
                // Y-axis labels
                ctx.fillStyle = this.config.theme.textColor || '#9ca3af';
                ctx.font = '10px sans-serif';
                ctx.textAlign = 'right';
                ctx.textBaseline = 'middle';
                ctx.fillText(label, padding.left - 10, padding.top + i * cellH + cellH / 2);
            });
        }
    }

    /**
     * Render correlation matrix
     */
    _renderCorrelation() {
        const data = this.config.data;
        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        const padding = { top: 40, right: 40, bottom: 40, left: 40 };

        const matrix = data.datasets[0].data;
        const size = matrix.length;

        const chartW = w - padding.left - padding.right;
        const chartH = h - padding.top - padding.bottom;
        const cellSize = Math.min(chartW / size, chartH / size);

        const offsetX = (chartW - cellSize * size) / 2;
        const offsetY = (chartH - cellSize * size) / 2;

        // Draw correlation matrix
        matrix.forEach((row, i) => {
            row.forEach((value, j) => {
                const x = padding.left + offsetX + j * cellSize;
                const y = padding.top + offsetY + i * cellSize;

                // Color based on correlation value (-1 to 1)
                const normalized = (value + 1) / 2;
                const r = Math.round((1 - normalized) * 255);
                const b = Math.round(normalized * 255);
                const g = Math.round(128 - Math.abs(normalized - 0.5) * 128);

                ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
                ctx.fillRect(x, y, cellSize, cellSize);

                // Draw value
                ctx.fillStyle = Math.abs(value) > 0.5 ? '#fff' : '#000';
                ctx.font = '10px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(value.toFixed(2), x + cellSize / 2, y + cellSize / 2);
            });
        });

        // Draw labels
        if (data.labels) {
            data.labels.forEach((label, i) => {
                // X-axis labels
                ctx.fillStyle = this.config.theme.textColor || '#9ca3af';
                ctx.font = '10px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillText(label, padding.left + offsetX + i * cellSize + cellSize / 2, h - padding.bottom + 5);

                // Y-axis labels
                ctx.fillStyle = this.config.theme.textColor || '#9ca3af';
                ctx.font = '10px sans-serif';
                ctx.textAlign = 'right';
                ctx.textBaseline = 'middle';
                ctx.fillText(label, padding.left - 10, padding.top + offsetY + i * cellSize + cellSize / 2);
            });
        }
    }

    // ============================================================
    // UTILITY FUNCTIONS
    // ============================================================

    /**
     * Draw chart axes
     */
    _drawAxes(ctx, padding, w, h, min, max) {
        ctx.strokeStyle = this.config.theme.borderColor || '#2d3f55';
        ctx.lineWidth = 1;

        // Y-axis
        ctx.beginPath();
        ctx.moveTo(padding.left, padding.top);
        ctx.lineTo(padding.left, h - padding.bottom);
        ctx.stroke();

        // X-axis
        ctx.beginPath();
        ctx.moveTo(padding.left, h - padding.bottom);
        ctx.lineTo(w - padding.right, h - padding.bottom);
        ctx.stroke();

        // Y-axis labels
        const numTicks = 5;
        const range = max - min || 1;
        for (let i = 0; i <= numTicks; i++) {
            const value = min + (i / numTicks) * range;
            const y = padding.top + (h - padding.top - padding.bottom) * (1 - i / numTicks);
            ctx.fillStyle = this.config.theme.textColor || '#9ca3af';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'right';
            ctx.textBaseline = 'middle';
            ctx.fillText(value.toFixed(2), padding.left - 10, y);
        }
    }

    /**
     * Draw chart grid
     */
    _drawGrid(ctx, padding, w, h, min, max) {
        ctx.strokeStyle = this.config.theme.gridColor || 'rgba(45, 63, 85, 0.3)';
        ctx.lineWidth = 0.5;

        const numLines = 5;
        const range = max - min || 1;
        for (let i = 0; i <= numLines; i++) {
            const y = padding.top + (h - padding.top - padding.bottom) * (1 - i / numLines);
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(w - padding.right, y);
            ctx.stroke();
        }
    }

    /**
     * Draw chart legend
     */
    _drawLegend(ctx, label, padding, index = 0) {
        const x = padding.left;
        const y = padding.top + index * 25;

        // Draw color box
        ctx.fillStyle = this._getColor(index);
        ctx.fillRect(x, y + 4, 12, 12);

        // Draw label
        ctx.fillStyle = this.config.theme.textColor || '#9ca3af';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, x + 18, y + 10);
    }

    /**
     * Get color by index
     */
    _getColor(index) {
        const colors = [
            '#00d4ff', '#7b2ffc', '#10b981', '#f59e0b', '#ef4444',
            '#3b82f6', '#ec4899', '#14b8a6', '#f97316', '#8b5cf6',
            '#06b6d4', '#84cc16', '#f472b6', '#6366f1', '#22d3ee',
        ];
        return colors[index % colors.length];
    }

    /**
     * Get default theme
     */
    _getDefaultTheme() {
        return {
            backgroundColor: '#0a0e1a',
            color: '#e5e7eb',
            textColor: '#9ca3af',
            borderColor: '#2d3f55',
            gridColor: 'rgba(45, 63, 85, 0.3)',
            positiveColor: '#00ff88',
            negativeColor: '#ff4444',
        };
    }

    // ============================================================
    // EVENT SYSTEM
    // ============================================================

    /**
     * Add event listener
     */
    on(event, listener) {
        if (!this._listeners) {
            this._listeners = {};
        }
        if (!this._listeners[event]) {
            this._listeners[event] = [];
        }
        this._listeners[event].push(listener);
    }

    /**
     * Remove event listener
     */
    off(event, listener) {
        if (this._listeners && this._listeners[event]) {
            const index = this._listeners[event].indexOf(listener);
            if (index !== -1) {
                this._listeners[event].splice(index, 1);
            }
        }
    }

    /**
     * Emit event
     */
    _emit(event, data) {
        if (this._listeners && this._listeners[event]) {
            this._listeners[event].forEach(listener => {
                try {
                    listener(data);
                } catch (error) {
                    this.log('Error in event listener:', error);
                }
            });
        }
    }

    // ============================================================
    // RESIZE HANDLING
    // ============================================================

    /**
     * Setup resize observer
     */
    _setupResizeObserver() {
        if (window.ResizeObserver) {
            this.resizeObserver = new ResizeObserver(() => {
                this._resizeCanvas();
                this.render({ force: true });
            });
            this.resizeObserver.observe(this.container);
        }
    }

    /**
     * Setup event handlers
     */
    _setupEventHandlers() {
        // Mouse events for tooltips
        this.canvas.addEventListener('mousemove', (e) => {
            // Handle mouse move for tooltips
        });

        this.canvas.addEventListener('click', (e) => {
            // Handle click for interactivity
        });
    }

    // ============================================================
    // LOGGING
    // ============================================================

    /**
     * Log message
     */
    log(...args) {
        console.log('[NexusChart]', ...args);
    }

    // ============================================================
    // CLEANUP
    // ============================================================

    /**
     * Destroy chart instance
     */
    destroy() {
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }

        this.canvas = null;
        this.ctx = null;
        this.isRendered = false;
        this._emit('destroy', { chart: this });

        this.log('Chart destroyed');
    }
}

// ============================================================
// CHART REGISTRY
// ============================================================

const ChartRegistry = {
    charts: new Map(),

    /**
     * Register a chart
     */
    register(id, chart) {
        this.charts.set(id, chart);
    },

    /**
     * Get a chart by ID
     */
    get(id) {
        return this.charts.get(id);
    },

    /**
     * Get all charts
     */
    getAll() {
        return Array.from(this.charts.values());
    },

    /**
     * Remove a chart
     */
    remove(id) {
        const chart = this.charts.get(id);
        if (chart) {
            chart.destroy();
            this.charts.delete(id);
        }
    },

    /**
     * Clear all charts
     */
    clear() {
        for (const [id, chart] of this.charts) {
            chart.destroy();
        }
        this.charts.clear();
    },
};

// ============================================================
// EXPORTS
// ============================================================

// Export for Node.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { NexusChart, ChartRegistry };
}

// Export for browser
if (typeof window !== 'undefined') {
    window.NexusChart = NexusChart;
    window.ChartRegistry = ChartRegistry;
}

export { NexusChart, ChartRegistry };

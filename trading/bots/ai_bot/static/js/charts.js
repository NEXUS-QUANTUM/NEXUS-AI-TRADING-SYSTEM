// trading/bots/ai_bot/static/js/charts.js
// NEXUS AI TRADING SYSTEM - Advanced Charting Library
// Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

/**
 * Advanced Charting Library for NEXUS AI Trading Bot
 * Provides comprehensive charting capabilities including:
 * - Candlestick charts (TradingView Lightweight Charts)
 * - Line charts
 * - Bar charts
 * - Volume charts
 * - RSI, MACD, Bollinger Bands indicators
 * - Real-time updates
 * - Multi-timeframe support
 * - Chart synchronization
 * - Export capabilities
 */

class NexusCharts {
    constructor(config = {}) {
        // Chart configuration
        this.container = config.container || 'chart-container';
        this.theme = config.theme || 'dark';
        this.timeframe = config.timeframe || '1h';
        this.symbol = config.symbol || 'BTC-USD';
        this.chartType = config.chartType || 'candlestick';
        this.height = config.height || '100%';
        this.width = config.width || '100%';
        this.colors = this.getThemeColors(this.theme);
        
        // Chart instances
        this.mainChart = null;
        this.volumeChart = null;
        this.indicatorCharts = {};
        this.overlays = {};
        
        // Data
        this.data = [];
        this.indicators = {};
        this.annotations = [];
        this.overlaysData = {};
        
        // State
        this.isRealTime = false;
        this.updateInterval = null;
        this.zoomLevel = 1;
        this.visibleRange = null;
        this.selectedCandle = null;
        
        // Event listeners
        this.eventListeners = {
            'candleClick': [],
            'rangeChange': [],
            'crosshairMove': [],
            'indicatorChange': [],
            'zoomChange': [],
        };
        
        // Indicator configurations
        this.indicatorConfigs = {
            rsi: {
                period: 14,
                overbought: 70,
                oversold: 30,
                color: '#FF6B6B',
                visible: false,
            },
            macd: {
                fastPeriod: 12,
                slowPeriod: 26,
                signalPeriod: 9,
                color: '#FFD93D',
                visible: false,
            },
            bollingerBands: {
                period: 20,
                stdDev: 2,
                color: '#6C5CE7',
                visible: false,
            },
            sma: {
                period: 20,
                color: '#FF6B6B',
                visible: false,
            },
            ema: {
                period: 20,
                color: '#4ECDC4',
                visible: false,
            },
            volume: {
                color: '#4ECDC4',
                visible: true,
            },
        };
        
        // Initialize chart
        this.initChart();
        
        logger.info('NexusCharts initialized', { symbol: this.symbol, timeframe: this.timeframe });
    }

    // ========================================================================
    // Chart Initialization
    // ========================================================================

    /**
     * Initialize main chart
     */
    initChart() {
        const container = document.getElementById(this.container);
        if (!container) {
            logger.error(`Chart container #${this.container} not found`);
            return;
        }

        // Create main chart container
        this.chartContainer = document.createElement('div');
        this.chartContainer.className = 'nexus-chart-container';
        this.chartContainer.style.width = this.width;
        this.chartContainer.style.height = this.height;
        this.chartContainer.style.position = 'relative';
        container.appendChild(this.chartContainer);

        // Create chart wrapper
        this.chartWrapper = document.createElement('div');
        this.chartWrapper.className = 'nexus-chart-wrapper';
        this.chartWrapper.style.width = '100%';
        this.chartWrapper.style.height = '100%';
        this.chartContainer.appendChild(this.chartWrapper);

        // Create main chart element
        this.mainChartElement = document.createElement('div');
        this.mainChartElement.className = 'nexus-main-chart';
        this.mainChartElement.style.width = '100%';
        this.mainChartElement.style.height = '70%';
        this.chartWrapper.appendChild(this.mainChartElement);

        // Create volume chart element
        this.volumeChartElement = document.createElement('div');
        this.volumeChartElement.className = 'nexus-volume-chart';
        this.volumeChartElement.style.width = '100%';
        this.volumeChartElement.style.height = '15%';
        this.chartWrapper.appendChild(this.volumeChartElement);

        // Create indicator charts container
        this.indicatorContainer = document.createElement('div');
        this.indicatorContainer.className = 'nexus-indicator-container';
        this.indicatorContainer.style.width = '100%';
        this.indicatorContainer.style.height = '15%';
        this.chartWrapper.appendChild(this.indicatorContainer);

        // Initialize lightweight charts
        this.initLightweightCharts();

        // Set up resize observer
        this.setupResizeObserver();

        // Set up theme observer
        this.setupThemeObserver();

        // Load initial data
        this.loadData();
    }

    /**
     * Initialize Lightweight Charts
     */
    initLightweightCharts() {
        // Check if Lightweight Charts is available
        if (typeof LightweightCharts === 'undefined') {
            logger.warn('Lightweight Charts library not loaded, falling back to Canvas');
            this.initCanvasChart();
            return;
        }

        try {
            // Main chart
            this.mainChart = LightweightCharts.createChart(this.mainChartElement, {
                width: this.mainChartElement.clientWidth || 800,
                height: this.mainChartElement.clientHeight || 400,
                layout: {
                    backgroundColor: this.colors.background,
                    textColor: this.colors.text,
                },
                grid: {
                    vertLines: {
                        color: this.colors.gridLines,
                    },
                    horzLines: {
                        color: this.colors.gridLines,
                    },
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                },
                rightPriceScale: {
                    borderColor: this.colors.border,
                    scaleMargins: {
                        top: 0.1,
                        bottom: 0.1,
                    },
                },
                timeScale: {
                    borderColor: this.colors.border,
                    timeVisible: true,
                    secondsVisible: false,
                    tickMarkFormatter: (time) => this.formatTimeLabel(time),
                },
                handleScroll: {
                    mouseWheel: true,
                    pressedMouseMove: true,
                },
                handleScale: {
                    axisPressedMouseMove: true,
                    mouseWheel: true,
                    pinch: true,
                },
            });

            // Volume chart
            this.volumeChart = LightweightCharts.createChart(this.volumeChartElement, {
                width: this.volumeChartElement.clientWidth || 800,
                height: this.volumeChartElement.clientHeight || 80,
                layout: {
                    backgroundColor: this.colors.background,
                    textColor: this.colors.text,
                },
                grid: {
                    vertLines: {
                        color: this.colors.gridLines,
                    },
                    horzLines: {
                        color: this.colors.gridLines,
                    },
                },
                rightPriceScale: {
                    borderColor: this.colors.border,
                    scaleMargins: {
                        top: 0.1,
                        bottom: 0.1,
                    },
                },
                timeScale: {
                    borderColor: this.colors.border,
                    visible: false,
                },
                handleScroll: false,
                handleScale: false,
            });

            // Sync time scales
            this.syncTimeScales();

            // Set up event handlers
            this.setupChartEvents();

            logger.info('Lightweight Charts initialized');
        } catch (error) {
            logger.error('Failed to initialize Lightweight Charts:', error);
            this.initCanvasChart();
        }
    }

    /**
     * Initialize Canvas chart (fallback)
     */
    initCanvasChart() {
        // Create canvas element
        this.canvas = document.createElement('canvas');
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.mainChartElement.appendChild(this.canvas);

        // Get context
        this.ctx = this.canvas.getContext('2d');

        // Set up resize handler
        this.setupCanvasResize();

        logger.info('Canvas chart initialized (fallback)');
    }

    // ========================================================================
    // Data Loading
    // ========================================================================

    /**
     * Load chart data
     * @param {string} symbol - Trading pair symbol
     * @param {string} timeframe - Timeframe (1m, 5m, 15m, 1h, 4h, 1d, 1w)
     * @param {number} limit - Number of candles
     */
    async loadData(symbol = null, timeframe = null, limit = 500) {
        this.symbol = symbol || this.symbol;
        this.timeframe = timeframe || this.timeframe;

        try {
            // Get data from API
            const data = await NexusAPI.getMarketData(this.symbol, this.timeframe, limit);
            
            if (data && data.candles) {
                this.data = this.parseCandleData(data.candles);
                this.renderChart();
                this.calculateIndicators();
            } else {
                // Load sample data for testing
                this.data = this.generateSampleData(limit);
                this.renderChart();
                this.calculateIndicators();
            }

            // Emit data loaded event
            this.emitEvent('dataLoaded', { symbol: this.symbol, timeframe: this.timeframe, count: this.data.length });
        } catch (error) {
            logger.error('Error loading chart data:', error);
            // Generate sample data as fallback
            this.data = this.generateSampleData(limit);
            this.renderChart();
            this.calculateIndicators();
        }
    }

    /**
     * Parse candle data from API
     * @param {Array} candles - Raw candle data
     * @returns {Array} Parsed candle data
     */
    parseCandleData(candles) {
        return candles.map(candle => ({
            time: Math.floor(new Date(candle.timestamp).getTime() / 1000),
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
            volume: candle.volume,
        }));
    }

    /**
     * Generate sample data for testing
     * @param {number} count - Number of candles
     * @returns {Array} Sample candle data
     */
    generateSampleData(count = 500) {
        const data = [];
        let price = 45000;
        const now = Math.floor(Date.now() / 1000);
        const interval = this.getTimeframeSeconds();

        for (let i = count - 1; i >= 0; i--) {
            const time = now - (i * interval);
            const change = (Math.random() - 0.5) * 200;
            const open = price;
            const close = price + change;
            const high = Math.max(open, close) + Math.random() * 100;
            const low = Math.min(open, close) - Math.random() * 100;
            const volume = Math.random() * 1000 + 100;

            data.push({
                time,
                open,
                high,
                low,
                close,
                volume,
            });

            price = close;
        }

        return data;
    }

    /**
     * Get timeframe interval in seconds
     * @returns {number} Interval in seconds
     */
    getTimeframeSeconds() {
        const intervals = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '1h': 3600,
            '4h': 14400,
            '1d': 86400,
            '1w': 604800,
        };
        return intervals[this.timeframe] || 3600;
    }

    // ========================================================================
    // Chart Rendering
    // ========================================================================

    /**
     * Render chart
     */
    renderChart() {
        if (this.mainChart) {
            this.renderLightweightChart();
        } else {
            this.renderCanvasChart();
        }
    }

    /**
     * Render with Lightweight Charts
     */
    renderLightweightChart() {
        if (!this.mainChart || !this.data.length) return;

        try {
            // Clear existing series
            this.mainChart.removeAllSeries();
            this.volumeChart.removeAllSeries();

            // Create candlestick series
            const candlestickSeries = this.mainChart.addCandlestickSeries({
                upColor: this.colors.candleUp,
                downColor: this.colors.candleDown,
                borderVisible: false,
                wickUpColor: this.colors.candleUp,
                wickDownColor: this.colors.candleDown,
                priceFormat: {
                    type: 'price',
                    precision: 2,
                    minMove: 0.01,
                },
            });

            // Set data
            candlestickSeries.setData(this.data);

            // Store series reference
            this.candlestickSeries = candlestickSeries;

            // Create volume series
            const volumeSeries = this.volumeChart.addHistogramSeries({
                color: this.colors.volume,
                priceFormat: {
                    type: 'volume',
                },
                scaleMargins: {
                    top: 0.1,
                    bottom: 0.1,
                },
            });

            // Set volume data
            const volumeData = this.data.map(candle => ({
                time: candle.time,
                value: candle.volume,
                color: candle.close >= candle.open ? this.colors.volumeUp : this.colors.volumeDown,
            }));
            volumeSeries.setData(volumeData);

            // Store series reference
            this.volumeSeries = volumeSeries;

            // Render indicators
            this.renderIndicators();

            // Render overlays
            this.renderOverlays();

            // Fit content
            this.mainChart.timeScale().fitContent();
            this.volumeChart.timeScale().fitContent();

        } catch (error) {
            logger.error('Error rendering Lightweight chart:', error);
        }
    }

    /**
     * Render with Canvas (fallback)
     */
    renderCanvasChart() {
        if (!this.canvas || !this.ctx || !this.data.length) return;

        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * window.devicePixelRatio;
        this.canvas.height = rect.height * window.devicePixelRatio;
        this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

        const width = rect.width;
        const height = rect.height;
        const padding = { top: 20, right: 20, bottom: 20, left: 60 };
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;

        // Clear canvas
        this.ctx.clearRect(0, 0, width, height);

        // Calculate min/max
        const minPrice = Math.min(...this.data.map(d => d.low));
        const maxPrice = Math.max(...this.data.map(d => d.high));
        const priceRange = maxPrice - minPrice;

        // Draw chart background
        this.ctx.fillStyle = this.colors.background;
        this.ctx.fillRect(0, 0, width, height);

        // Draw grid
        this.drawGrid(width, height, padding, chartWidth, chartHeight, minPrice, maxPrice);

        // Draw candles
        this.drawCandles(padding, chartWidth, chartHeight, minPrice, priceRange);

        // Draw price labels
        this.drawPriceLabels(padding, chartHeight, minPrice, maxPrice);

        // Draw time labels
        this.drawTimeLabels(padding, chartWidth, chartHeight);
    }

    /**
     * Draw grid
     */
    drawGrid(width, height, padding, chartWidth, chartHeight, minPrice, maxPrice) {
        const ctx = this.ctx;
        const gridLines = 8;

        // Horizontal grid lines
        for (let i = 0; i <= gridLines; i++) {
            const y = padding.top + (i / gridLines) * chartHeight;
            const price = maxPrice - (i / gridLines) * (maxPrice - minPrice);
            
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(width - padding.right, y);
            ctx.strokeStyle = this.colors.gridLines;
            ctx.lineWidth = 0.5;
            ctx.stroke();

            // Price label
            ctx.fillStyle = this.colors.text;
            ctx.font = '10px Arial';
            ctx.textAlign = 'right';
            ctx.textBaseline = 'middle';
            ctx.fillText(price.toFixed(2), padding.left - 5, y);
        }

        // Vertical grid lines
        const candleWidth = chartWidth / this.data.length;
        const step = Math.max(1, Math.floor(this.data.length / 20));
        for (let i = 0; i < this.data.length; i += step) {
            const x = padding.left + i * candleWidth;
            ctx.beginPath();
            ctx.moveTo(x, padding.top);
            ctx.lineTo(x, padding.top + chartHeight);
            ctx.strokeStyle = this.colors.gridLines;
            ctx.lineWidth = 0.5;
            ctx.stroke();
        }
    }

    /**
     * Draw candles
     */
    drawCandles(padding, chartWidth, chartHeight, minPrice, priceRange) {
        const ctx = this.ctx;
        const candleWidth = Math.max(2, chartWidth / this.data.length * 0.8);
        const halfCandle = candleWidth / 2;

        this.data.forEach((candle, index) => {
            const x = padding.left + index * (chartWidth / this.data.length) + halfCandle;
            const yHigh = padding.top + ((maxPrice - candle.high) / priceRange) * chartHeight;
            const yLow = padding.top + ((maxPrice - candle.low) / priceRange) * chartHeight;
            const yOpen = padding.top + ((maxPrice - candle.open) / priceRange) * chartHeight;
            const yClose = padding.top + ((maxPrice - candle.close) / priceRange) * chartHeight;

            const color = candle.close >= candle.open ? this.colors.candleUp : this.colors.candleDown;

            // Draw wick
            ctx.beginPath();
            ctx.moveTo(x, yHigh);
            ctx.lineTo(x, yLow);
            ctx.strokeStyle = color;
            ctx.lineWidth = 1;
            ctx.stroke();

            // Draw body
            const bodyTop = Math.min(yOpen, yClose);
            const bodyBottom = Math.max(yOpen, yClose);
            const bodyHeight = Math.max(1, bodyBottom - bodyTop);

            ctx.fillStyle = color;
            ctx.fillRect(x - halfCandle, bodyTop, candleWidth, bodyHeight);

            // Draw border
            ctx.strokeStyle = color;
            ctx.lineWidth = 0.5;
            ctx.strokeRect(x - halfCandle, bodyTop, candleWidth, bodyHeight);
        });
    }

    /**
     * Draw price labels
     */
    drawPriceLabels(padding, chartHeight, minPrice, maxPrice) {
        // Already drawn in grid
    }

    /**
     * Draw time labels
     */
    drawTimeLabels(padding, chartWidth, chartHeight) {
        const ctx = this.ctx;
        const step = Math.max(1, Math.floor(this.data.length / 10));

        for (let i = 0; i < this.data.length; i += step) {
            const x = padding.left + i * (chartWidth / this.data.length);
            const date = new Date(this.data[i].time * 1000);
            const label = this.formatDateLabel(date);

            ctx.fillStyle = this.colors.text;
            ctx.font = '9px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            ctx.fillText(label, x, padding.top + chartHeight + 5);
        }
    }

    /**
     * Setup canvas resize
     */
    setupCanvasResize() {
        const resizeObserver = new ResizeObserver(() => {
            if (this.canvas) {
                this.renderCanvasChart();
            }
        });
        resizeObserver.observe(this.canvas);
    }

    // ========================================================================
    // Indicators
    // ========================================================================

    /**
     * Calculate indicators
     */
    calculateIndicators() {
        if (!this.data.length) return;

        // Calculate RSI
        if (this.indicatorConfigs.rsi.visible) {
            this.indicators.rsi = this.calculateRSI(this.indicatorConfigs.rsi.period);
        }

        // Calculate MACD
        if (this.indicatorConfigs.macd.visible) {
            this.indicators.macd = this.calculateMACD(
                this.indicatorConfigs.macd.fastPeriod,
                this.indicatorConfigs.macd.slowPeriod,
                this.indicatorConfigs.macd.signalPeriod
            );
        }

        // Calculate Bollinger Bands
        if (this.indicatorConfigs.bollingerBands.visible) {
            this.indicators.bollingerBands = this.calculateBollingerBands(
                this.indicatorConfigs.bollingerBands.period,
                this.indicatorConfigs.bollingerBands.stdDev
            );
        }

        // Calculate SMA
        if (this.indicatorConfigs.sma.visible) {
            this.indicators.sma = this.calculateSMA(this.indicatorConfigs.sma.period);
        }

        // Calculate EMA
        if (this.indicatorConfigs.ema.visible) {
            this.indicators.ema = this.calculateEMA(this.indicatorConfigs.ema.period);
        }

        // Render indicators
        this.renderIndicators();
    }

    /**
     * Calculate RSI
     * @param {number} period - RSI period
     * @returns {Array} RSI values
     */
    calculateRSI(period = 14) {
        const closes = this.data.map(d => d.close);
        const rsi = [];
        let avgGain = 0;
        let avgLoss = 0;

        // Calculate initial average gain/loss
        for (let i = 1; i < period; i++) {
            const change = closes[i] - closes[i - 1];
            if (change >= 0) {
                avgGain += change;
            } else {
                avgLoss += Math.abs(change);
            }
        }

        avgGain /= period;
        avgLoss /= period;

        rsi.push(100 - (100 / (1 + (avgGain / (avgLoss || 1)))));

        // Calculate RSI for remaining periods
        for (let i = period + 1; i < closes.length; i++) {
            const change = closes[i] - closes[i - 1];
            if (change >= 0) {
                avgGain = (avgGain * (period - 1) + change) / period;
                avgLoss = (avgLoss * (period - 1)) / period;
            } else {
                avgGain = (avgGain * (period - 1)) / period;
                avgLoss = (avgLoss * (period - 1) + Math.abs(change)) / period;
            }

            const rs = avgGain / (avgLoss || 1);
            rsi.push(100 - (100 / (1 + rs)));
        }

        return rsi;
    }

    /**
     * Calculate MACD
     * @param {number} fastPeriod - Fast EMA period
     * @param {number} slowPeriod - Slow EMA period
     * @param {number} signalPeriod - Signal period
     * @returns {Object} MACD values
     */
    calculateMACD(fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
        const closes = this.data.map(d => d.close);
        const fastEMA = this.calculateEMAFromValues(closes, fastPeriod);
        const slowEMA = this.calculateEMAFromValues(closes, slowPeriod);
        const macdLine = fastEMA.map((v, i) => v - slowEMA[i]);
        const signalLine = this.calculateEMAFromValues(macdLine, signalPeriod);
        const histogram = macdLine.map((v, i) => v - signalLine[i]);

        return { macdLine, signalLine, histogram };
    }

    /**
     * Calculate Bollinger Bands
     * @param {number} period - SMA period
     * @param {number} stdDev - Standard deviation multiplier
     * @returns {Object} Bollinger Bands
     */
    calculateBollingerBands(period = 20, stdDev = 2) {
        const closes = this.data.map(d => d.close);
        const sma = this.calculateSMAFromValues(closes, period);
        const upper = [];
        const lower = [];

        for (let i = 0; i < closes.length; i++) {
            if (i < period - 1) {
                upper.push(null);
                lower.push(null);
                continue;
            }

            const slice = closes.slice(i - period + 1, i + 1);
            const mean = slice.reduce((a, b) => a + b, 0) / period;
            const variance = slice.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / period;
            const std = Math.sqrt(variance);

            upper.push(mean + stdDev * std);
            lower.push(mean - stdDev * std);
        }

        return { upper, middle: sma, lower };
    }

    /**
     * Calculate SMA
     * @param {number} period - SMA period
     * @returns {Array} SMA values
     */
    calculateSMA(period = 20) {
        const closes = this.data.map(d => d.close);
        return this.calculateSMAFromValues(closes, period);
    }

    /**
     * Calculate SMA from values
     * @param {Array} values - Values
     * @param {number} period - SMA period
     * @returns {Array} SMA values
     */
    calculateSMAFromValues(values, period = 20) {
        const sma = [];
        for (let i = 0; i < values.length; i++) {
            if (i < period - 1) {
                sma.push(null);
                continue;
            }
            const sum = values.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
            sma.push(sum / period);
        }
        return sma;
    }

    /**
     * Calculate EMA
     * @param {number} period - EMA period
     * @returns {Array} EMA values
     */
    calculateEMA(period = 20) {
        const closes = this.data.map(d => d.close);
        return this.calculateEMAFromValues(closes, period);
    }

    /**
     * Calculate EMA from values
     * @param {Array} values - Values
     * @param {number} period - EMA period
     * @returns {Array} EMA values
     */
    calculateEMAFromValues(values, period = 20) {
        const ema = [];
        const multiplier = 2 / (period + 1);

        for (let i = 0; i < values.length; i++) {
            if (i === 0) {
                ema.push(values[i]);
            } else if (i < period - 1) {
                ema.push(values[i]);
            } else {
                const emaPrev = ema[i - 1];
                const price = values[i];
                ema.push((price - emaPrev) * multiplier + emaPrev);
            }
        }

        return ema;
    }

    /**
     * Render indicators on chart
     */
    renderIndicators() {
        if (!this.mainChart) return;

        try {
            // Remove existing indicator series
            if (this.indicatorSeries) {
                this.indicatorSeries.forEach(series => {
                    this.mainChart.removeSeries(series);
                });
            }
            this.indicatorSeries = [];

            // RSI indicator
            if (this.indicatorConfigs.rsi.visible && this.indicators.rsi) {
                const rsiSeries = this.mainChart.addLineSeries({
                    color: this.indicatorConfigs.rsi.color,
                    lineWidth: 2,
                    priceFormat: {
                        type: 'price',
                        precision: 2,
                    },
                    scaleMargins: {
                        top: 0.8,
                        bottom: 0.1,
                    },
                });

                const rsiData = this.data.map((candle, i) => ({
                    time: candle.time,
                    value: this.indicators.rsi[i] || 0,
                }));

                rsiSeries.setData(rsiData);
                this.indicatorSeries.push(rsiSeries);
            }

            // MACD indicator
            if (this.indicatorConfigs.macd.visible && this.indicators.macd) {
                const macdData = this.data.map((candle, i) => ({
                    time: candle.time,
                    value: this.indicators.macd.macdLine[i] || 0,
                }));

                const signalData = this.data.map((candle, i) => ({
                    time: candle.time,
                    value: this.indicators.macd.signalLine[i] || 0,
                }));

                const macdSeries = this.mainChart.addLineSeries({
                    color: '#FFD93D',
                    lineWidth: 2,
                    priceFormat: {
                        type: 'price',
                        precision: 4,
                    },
                    scaleMargins: {
                        top: 0.8,
                        bottom: 0.1,
                    },
                });

                const signalSeries = this.mainChart.addLineSeries({
                    color: '#6C5CE7',
                    lineWidth: 1,
                    priceFormat: {
                        type: 'price',
                        precision: 4,
                    },
                });

                macdSeries.setData(macdData);
                signalSeries.setData(signalData);
                this.indicatorSeries.push(macdSeries, signalSeries);

                // Add histogram
                const histogramData = this.data.map((candle, i) => ({
                    time: candle.time,
                    value: this.indicators.macd.histogram[i] || 0,
                }));

                const histogramSeries = this.mainChart.addHistogramSeries({
                    color: '#FF6B6B',
                    priceFormat: {
                        type: 'price',
                        precision: 4,
                    },
                });

                histogramSeries.setData(histogramData);
                this.indicatorSeries.push(histogramSeries);
            }

            // Bollinger Bands
            if (this.indicatorConfigs.bollingerBands.visible && this.indicators.bollingerBands) {
                const upperData = this.data.map((candle, i) => ({
                    time: candle.time,
                    value: this.indicators.bollingerBands.upper[i] || 0,
                }));

                const middleData = this.data.map((candle, i) => ({
                    time: candle.time,
                    value: this.indicators.bollingerBands.middle[i] || 0,
                }));

                const lowerData = this.data.map((candle, i) => ({
                    time: candle.time,
                    value: this.indicators.bollingerBands.lower[i] || 0,
                }));

                const upperSeries = this.mainChart.addLineSeries({
                    color: '#6C5CE7',
                    lineWidth: 1,
                    priceFormat: {
                        type: 'price',
                        precision: 2,
                    },
                });

                const middleSeries = this.mainChart.addLineSeries({
                    color: '#6C5CE7',
                    lineWidth: 2,
                    priceFormat: {
                        type: 'price',
                        precision: 2,
                    },
                });

                const lowerSeries = this.mainChart.addLineSeries({
                    color: '#6C5CE7',
                    lineWidth: 1,
                    priceFormat: {
                        type: 'price',
                        precision: 2,
                    },
                });

                upperSeries.setData(upperData);
                middleSeries.setData(middleData);
                lowerSeries.setData(lowerData);
                this.indicatorSeries.push(upperSeries, middleSeries, lowerSeries);
            }

            // SMA
            if (this.indicatorConfigs.sma.visible && this.indicators.sma) {
                const smaData = this.data.map((candle, i) => ({
                    time: candle.time,
                    value: this.indicators.sma[i] || 0,
                }));

                const smaSeries = this.mainChart.addLineSeries({
                    color: this.indicatorConfigs.sma.color,
                    lineWidth: 2,
                    priceFormat: {
                        type: 'price',
                        precision: 2,
                    },
                });

                smaSeries.setData(smaData);
                this.indicatorSeries.push(smaSeries);
            }

            // EMA
            if (this.indicatorConfigs.ema.visible && this.indicators.ema) {
                const emaData = this.data.map((candle, i) => ({
                    time: candle.time,
                    value: this.indicators.ema[i] || 0,
                }));

                const emaSeries = this.mainChart.addLineSeries({
                    color: this.indicatorConfigs.ema.color,
                    lineWidth: 2,
                    priceFormat: {
                        type: 'price',
                        precision: 2,
                    },
                });

                emaSeries.setData(emaData);
                this.indicatorSeries.push(emaSeries);
            }

        } catch (error) {
            logger.error('Error rendering indicators:', error);
        }
    }

    // ========================================================================
    // Chart Controls
    // ========================================================================

    /**
     * Set chart type
     * @param {string} type - Chart type (candlestick, line, bar)
     */
    setChartType(type) {
        this.chartType = type;
        this.renderChart();
    }

    /**
     * Set timeframe
     * @param {string} timeframe - Timeframe (1m, 5m, 15m, 1h, 4h, 1d, 1w)
     */
    setTimeframe(timeframe) {
        this.timeframe = timeframe;
        this.loadData();
    }

    /**
     * Set symbol
     * @param {string} symbol - Trading pair symbol
     */
    setSymbol(symbol) {
        this.symbol = symbol;
        this.loadData();
    }

    /**
     * Toggle indicator visibility
     * @param {string} indicator - Indicator name
     */
    toggleIndicator(indicator) {
        if (this.indicatorConfigs[indicator]) {
            this.indicatorConfigs[indicator].visible = !this.indicatorConfigs[indicator].visible;
            this.calculateIndicators();
            this.emitEvent('indicatorChange', { indicator, visible: this.indicatorConfigs[indicator].visible });
        }
    }

    /**
     * Set indicator configuration
     * @param {string} indicator - Indicator name
     * @param {Object} config - Indicator configuration
     */
    setIndicatorConfig(indicator, config) {
        if (this.indicatorConfigs[indicator]) {
            this.indicatorConfigs[indicator] = { ...this.indicatorConfigs[indicator], ...config };
            this.calculateIndicators();
        }
    }

    /**
     * Enable real-time updates
     * @param {number} interval - Update interval in seconds
     */
    enableRealTime(interval = 5) {
        if (this.isRealTime) return;

        this.isRealTime = true;
        this.updateInterval = setInterval(() => {
            this.updateLastCandle();
        }, interval * 1000);

        logger.info('Real-time updates enabled');
    }

    /**
     * Disable real-time updates
     */
    disableRealTime() {
        this.isRealTime = false;
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        logger.info('Real-time updates disabled');
    }

    /**
     * Update last candle with new data
     */
    async updateLastCandle() {
        try {
            const data = await NexusAPI.getMarketData(this.symbol, this.timeframe, 1);
            if (data && data.candles && data.candles.length > 0) {
                const newCandle = data.candles[0];
                const candle = {
                    time: Math.floor(new Date(newCandle.timestamp).getTime() / 1000),
                    open: newCandle.open,
                    high: newCandle.high,
                    low: newCandle.low,
                    close: newCandle.close,
                    volume: newCandle.volume,
                };

                // Update last candle
                if (this.data.length > 0) {
                    const last = this.data[this.data.length - 1];
                    if (candle.time === last.time) {
                        // Update existing candle
                        this.data[this.data.length - 1] = candle;
                    } else {
                        // Add new candle
                        this.data.push(candle);
                        if (this.data.length > 1000) {
                            this.data.shift();
                        }
                    }
                } else {
                    this.data.push(candle);
                }

                // Update chart
                this.renderChart();
                this.calculateIndicators();

                this.emitEvent('candleUpdate', candle);
            }
        } catch (error) {
            logger.error('Error updating last candle:', error);
        }
    }

    /**
     * Fit content to view
     */
    fitContent() {
        if (this.mainChart) {
            this.mainChart.timeScale().fitContent();
            this.volumeChart.timeScale().fitContent();
        }
    }

    /**
     * Zoom in
     */
    zoomIn() {
        if (this.mainChart) {
            const timeScale = this.mainChart.timeScale();
            const range = timeScale.getVisibleRange();
            if (range) {
                const from = range.from;
                const to = range.to;
                const center = (from + to) / 2;
                const newRange = (to - from) * 0.8;
                timeScale.setVisibleRange({
                    from: center - newRange / 2,
                    to: center + newRange / 2,
                });
            }
            this.emitEvent('zoomChange', { direction: 'in' });
        }
    }

    /**
     * Zoom out
     */
    zoomOut() {
        if (this.mainChart) {
            const timeScale = this.mainChart.timeScale();
            const range = timeScale.getVisibleRange();
            if (range) {
                const from = range.from;
                const to = range.to;
                const center = (from + to) / 2;
                const newRange = (to - from) * 1.2;
                timeScale.setVisibleRange({
                    from: center - newRange / 2,
                    to: center + newRange / 2,
                });
            }
            this.emitEvent('zoomChange', { direction: 'out' });
        }
    }

    /**
     * Go to last candle
     */
    goToLastCandle() {
        if (this.mainChart) {
            const timeScale = this.mainChart.timeScale();
            const lastIndex = this.data.length - 1;
            const lastTime = this.data[lastIndex]?.time || 0;
            const range = timeScale.getVisibleRange();
            if (range && lastTime > range.to) {
                const diff = lastTime - range.to;
                timeScale.setVisibleRange({
                    from: range.from + diff,
                    to: range.to + diff,
                });
            }
        }
    }

    // ========================================================================
    // Chart Synchronization
    // ========================================================================

    /**
     * Sync time scales between main and volume charts
     */
    syncTimeScales() {
        if (this.mainChart && this.volumeChart) {
            this.mainChart.timeScale().subscribeVisibleTimeRangeChange((range) => {
                if (range) {
                    this.volumeChart.timeScale().setVisibleRange(range);
                }
            });

            this.volumeChart.timeScale().subscribeVisibleTimeRangeChange((range) => {
                if (range) {
                    this.mainChart.timeScale().setVisibleRange(range);
                }
            });
        }
    }

    // ========================================================================
    // Event System
    // ========================================================================

    /**
     * Setup chart events
     */
    setupChartEvents() {
        if (!this.mainChart) return;

        // Crosshair move
        this.mainChart.subscribeCrosshairMove((param) => {
            if (param) {
                const time = param.time;
                const price = param.seriesPrices;
                this.emitEvent('crosshairMove', { time, price, param });
            }
        });

        // Candle click
        // Note: Lightweight Charts doesn't have a direct click event
        // We'll use the crosshair move with click detection
        let clickTimeout = null;
        let clickTime = null;

        this.mainChartElement.addEventListener('click', (e) => {
            const rect = this.mainChartElement.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width;
            const timeScale = this.mainChart.timeScale();
            const range = timeScale.getVisibleRange();
            
            if (range && this.data.length > 0) {
                const from = range.from;
                const to = range.to;
                const time = from + (to - from) * x;
                const candle = this.findClosestCandle(time);
                
                if (candle) {
                    this.selectedCandle = candle;
                    this.emitEvent('candleClick', { candle, event: e });
                }
            }
        });

        // Resize handler
        const resizeObserver = new ResizeObserver(() => {
            this.resizeChart();
        });
        resizeObserver.observe(this.mainChartElement);
    }

    /**
     * Find closest candle to time
     * @param {number} time - Time to search
     * @returns {Object} Closest candle
     */
    findClosestCandle(time) {
        if (!this.data.length) return null;

        let closest = this.data[0];
        let minDiff = Math.abs(time - closest.time);

        for (let i = 1; i < this.data.length; i++) {
            const diff = Math.abs(time - this.data[i].time);
            if (diff < minDiff) {
                minDiff = diff;
                closest = this.data[i];
            }
        }

        return closest;
    }

    /**
     * Resize chart
     */
    resizeChart() {
        if (this.mainChart) {
            const width = this.mainChartElement.clientWidth;
            const height = this.mainChartElement.clientHeight;
            this.mainChart.resize(width, height);
            
            if (this.volumeChart) {
                const vWidth = this.volumeChartElement.clientWidth;
                const vHeight = this.volumeChartElement.clientHeight;
                this.volumeChart.resize(vWidth, vHeight);
            }
        }
    }

    /**
     * Setup resize observer
     */
    setupResizeObserver() {
        const resizeObserver = new ResizeObserver(() => {
            this.resizeChart();
        });
        resizeObserver.observe(this.chartContainer);
    }

    /**
     * Setup theme observer
     */
    setupThemeObserver() {
        // Watch for theme changes in the app
        const observer = new MutationObserver(() => {
            const theme = document.documentElement.getAttribute('data-theme') || 'dark';
            this.setTheme(theme);
        });
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    }

    // ========================================================================
    // Theme Management
    // ========================================================================

    /**
     * Get theme colors
     * @param {string} theme - Theme name
     * @returns {Object} Theme colors
     */
    getThemeColors(theme) {
        const colors = {
            dark: {
                background: '#1a1a2e',
                text: '#e0e0e0',
                gridLines: '#2d2d44',
                border: '#3d3d5c',
                candleUp: '#00c853',
                candleDown: '#ff1744',
                volume: '#4ECDC4',
                volumeUp: '#00c853',
                volumeDown: '#ff1744',
                indicatorPositive: '#00c853',
                indicatorNegative: '#ff1744',
            },
            light: {
                background: '#ffffff',
                text: '#1a1a2e',
                gridLines: '#e0e0e0',
                border: '#cccccc',
                candleUp: '#00c853',
                candleDown: '#ff1744',
                volume: '#4ECDC4',
                volumeUp: '#00c853',
                volumeDown: '#ff1744',
                indicatorPositive: '#00c853',
                indicatorNegative: '#ff1744',
            },
        };
        return colors[theme] || colors.dark;
    }

    /**
     * Set theme
     * @param {string} theme - Theme name
     */
    setTheme(theme) {
        this.theme = theme;
        this.colors = this.getThemeColors(theme);
        this.renderChart();
    }

    // ========================================================================
    // Utility Methods
    // ========================================================================

    /**
     * Format time label for chart
     * @param {number} time - Unix timestamp
     * @returns {string} Formatted label
     */
    formatTimeLabel(time) {
        const date = new Date(time * 1000);
        return this.formatDateLabel(date);
    }

    /**
     * Format date label
     * @param {Date} date - Date object
     * @returns {string} Formatted label
     */
    formatDateLabel(date) {
        const options = {
            '1m': { hour: '2-digit', minute: '2-digit' },
            '5m': { hour: '2-digit', minute: '2-digit' },
            '15m': { hour: '2-digit', minute: '2-digit' },
            '30m': { hour: '2-digit', minute: '2-digit' },
            '1h': { hour: '2-digit', minute: '2-digit' },
            '4h': { day: '2-digit', month: '2-digit', hour: '2-digit' },
            '1d': { day: '2-digit', month: '2-digit', year: 'numeric' },
            '1w': { day: '2-digit', month: '2-digit', year: 'numeric' },
        };
        const format = options[this.timeframe] || options['1h'];
        return date.toLocaleString('en-US', format);
    }

    /**
     * Export chart as image
     * @param {string} format - Image format (png, jpeg)
     * @param {number} quality - Image quality (0-1)
     * @returns {string} Data URL
     */
    exportImage(format = 'png', quality = 1) {
        if (this.canvas) {
            return this.canvas.toDataURL(`image/${format}`, quality);
        }

        // For Lightweight Charts, use the exported API if available
        if (this.mainChart && typeof this.mainChart.takeScreenshot === 'function') {
            return this.mainChart.takeScreenshot();
        }

        // Fallback: capture the chart container
        return this.captureContainer();
    }

    /**
     * Capture container as image
     * @returns {string} Data URL
     */
    captureContainer() {
        // Use html2canvas if available
        if (typeof html2canvas !== 'undefined') {
            return new Promise((resolve) => {
                html2canvas(this.chartContainer).then(canvas => {
                    resolve(canvas.toDataURL('image/png'));
                });
            });
        }
        return null;
    }

    /**
     * Add event listener
     * @param {string} event - Event name
     * @param {Function} listener - Event listener
     */
    on(event, listener) {
        if (this.eventListeners[event]) {
            this.eventListeners[event].push(listener);
        }
    }

    /**
     * Remove event listener
     * @param {string} event - Event name
     * @param {Function} listener - Event listener (optional)
     */
    off(event, listener = null) {
        if (this.eventListeners[event]) {
            if (listener) {
                const index = this.eventListeners[event].indexOf(listener);
                if (index !== -1) {
                    this.eventListeners[event].splice(index, 1);
                }
            } else {
                this.eventListeners[event] = [];
            }
        }
    }

    /**
     * Emit event
     * @param {string} event - Event name
     * @param {*} data - Event data
     */
    emitEvent(event, data) {
        if (this.eventListeners[event]) {
            this.eventListeners[event].forEach(listener => {
                try {
                    listener(data);
                } catch (error) {
                    logger.error(`Event listener error for ${event}:`, error);
                }
            });
        }
    }

    /**
     * Get chart data
     * @returns {Array} Chart data
     */
    getData() {
        return this.data;
    }

    /**
     * Get indicator data
     * @param {string} indicator - Indicator name
     * @returns {*} Indicator data
     */
    getIndicatorData(indicator) {
        return this.indicators[indicator];
    }

    /**
     * Destroy chart
     */
    destroy() {
        this.disableRealTime();

        if (this.mainChart) {
            this.mainChart.removeAllSeries();
            this.mainChart = null;
        }
        if (this.volumeChart) {
            this.volumeChart.removeAllSeries();
            this.volumeChart = null;
        }

        this.data = [];
        this.indicators = {};

        if (this.chartContainer) {
            this.chartContainer.innerHTML = '';
        }

        logger.info('Chart destroyed');
    }

    /**
     * Cleanup resources
     */
    cleanup() {
        this.destroy();
        this.eventListeners = {};
    }
}

// Create global chart instance
window.NexusCharts = NexusCharts;

// Simple logger
const logger = {
    debug: (...args) => console.debug('[DEBUG]', ...args),
    info: (...args) => console.info('[INFO]', ...args),
    warn: (...args) => console.warn('[WARN]', ...args),
    error: (...args) => console.error('[ERROR]', ...args),
};

export default NexusCharts;

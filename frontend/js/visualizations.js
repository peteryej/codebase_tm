/**
 * Visualization Manager for Codebase Time Machine
 */

class VisualizationManager {
    constructor(repositoryId) {
        this.repositoryId = repositoryId;
        this.currentVisualization = 'timeline';
        this.charts = {};
        
        this.init();
    }

    /**
     * Initialize visualization manager
     */
    init() {
        this.setupEventListeners();
        this.setupChartDefaults();
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        const vizSelector = document.getElementById('viz-selector');
        
        if (vizSelector) {
            vizSelector.addEventListener('change', (e) => {
                this.switchVisualization(e.target.value);
            });
        }
    }

    /**
     * Setup Chart.js defaults
     */
    setupChartDefaults() {
        if (typeof Chart !== 'undefined') {
            Chart.defaults.responsive = true;
            Chart.defaults.maintainAspectRatio = false;
            Chart.defaults.plugins.legend.display = true;
            Chart.defaults.plugins.tooltip.enabled = true;
        }
    }

    /**
     * Load initial visualization
     */
    async loadInitialVisualization() {
        await this.switchVisualization('timeline');
    }

    /**
     * Switch to different visualization
     */
    async switchVisualization(type) {
        this.currentVisualization = type;
        this.showLoading(true);

        try {
            switch (type) {
                case 'timeline':
                    await this.loadTimelineVisualization();
                    break;
                case 'contributors':
                    await this.loadContributorsVisualization();
                    break;
                case 'ownership':
                    await this.loadOwnershipVisualization();
                    break;
                case 'activity':
                    await this.loadActivityVisualization();
                    break;
                case 'languages':
                    await this.loadLanguagesVisualization();
                    break;
                default:
                    throw new Error(`Unknown visualization type: ${type}`);
            }
        } catch (error) {
            console.error(`Error loading ${type} visualization:`, error);
            this.showError(`Failed to load ${type} visualization: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * Load timeline visualization
     */
    async loadTimelineVisualization() {
        const data = await api.getTimelineData(this.repositoryId, 90, 'daily');
        
        this.hideAllContainers();
        this.showContainer('main-chart');

        const ctx = document.getElementById('main-chart');
        if (!ctx) return;

        // Destroy any existing chart on the main canvas
        this.destroyMainCanvasChart();

        const chartData = {
            labels: data.timeline.map(point => new Date(point.date).toLocaleDateString()),
            datasets: [{
                label: 'Commits',
                data: data.timeline.map(point => point.commits),
                borderColor: CONFIG.CHARTS.TIMELINE.BORDER_COLOR,
                backgroundColor: CONFIG.CHARTS.TIMELINE.BACKGROUND_COLOR,
                pointBackgroundColor: CONFIG.CHARTS.TIMELINE.POINT_BACKGROUND_COLOR,
                pointBorderColor: CONFIG.CHARTS.TIMELINE.POINT_BORDER_COLOR,
                fill: true,
                tension: 0.4
            }]
        };

        this.charts.timeline = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Number of Commits'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Date'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: `Commit Timeline (Last ${data.days} days)`
                    },
                    legend: {
                        display: false
                    }
                }
            }
        });
    }

    /**
     * Load contributors visualization
     */
    async loadContributorsVisualization() {
        const data = await api.getContributorsData(this.repositoryId, 10, 'commits');
        
        this.hideAllContainers();
        this.showContainer('main-chart');

        const ctx = document.getElementById('main-chart');
        if (!ctx) return;

        // Destroy any existing chart on the main canvas
        this.destroyMainCanvasChart();

        const chartData = {
            labels: data.chart_data.labels,
            datasets: data.chart_data.datasets.map(dataset => ({
                ...dataset,
                backgroundColor: CONFIG.CHARTS.CONTRIBUTORS.BACKGROUND_COLORS
            }))
        };

        this.charts.contributors = new Chart(ctx, {
            type: 'bar',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Number of Commits'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Contributors'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: `Top ${data.chart_data.labels.length} Contributors`
                    }
                }
            }
        });
    }

    /**
     * Load ownership visualization (heatmap)
     */
    async loadOwnershipVisualization() {
        const data = await api.getHeatmapData(this.repositoryId, 5, 50);
        
        this.hideAllContainers();
        this.showContainer('heatmap-container');

        const container = document.getElementById('heatmap-container');
        if (!container) return;

        // Clear existing content
        container.innerHTML = '';

        if (!data.heatmap || data.heatmap.length === 0) {
            container.innerHTML = '<p>No ownership data available</p>';
            return;
        }

        // Create heatmap using D3.js if available
        if (typeof d3 !== 'undefined') {
            this.createD3Heatmap(container, data.heatmap);
        } else {
            // Fallback to simple HTML representation
            this.createSimpleHeatmap(container, data.heatmap);
        }
    }

    /**
     * Create D3.js heatmap
     */
    createD3Heatmap(container, heatmapData) {
        const margin = { top: 50, right: 50, bottom: 100, left: 100 };
        const width = 800 - margin.left - margin.right;
        const height = 400 - margin.top - margin.bottom;

        // Clear container
        d3.select(container).selectAll("*").remove();

        const svg = d3.select(container)
            .append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`);

        // Prepare data
        const files = [...new Set(heatmapData.flatMap(dir => dir.files.map(f => f.file_path)))];
        const authors = [...new Set(heatmapData.flatMap(dir => dir.files.map(f => f.author)))];

        // Create scales
        const xScale = d3.scaleBand()
            .range([0, width])
            .domain(files.slice(0, 20)) // Limit to first 20 files
            .padding(0.1);

        const yScale = d3.scaleBand()
            .range([height, 0])
            .domain(authors.slice(0, 10)) // Limit to first 10 authors
            .padding(0.1);

        const colorScale = d3.scaleSequential()
            .interpolator(d3.interpolateBlues)
            .domain([0, 100]);

        // Create heatmap rectangles
        const heatmapItems = [];
        heatmapData.forEach(dir => {
            dir.files.forEach(file => {
                if (files.slice(0, 20).includes(file.file_path) && 
                    authors.slice(0, 10).includes(file.author)) {
                    heatmapItems.push(file);
                }
            });
        });

        svg.selectAll(".heatmap-rect")
            .data(heatmapItems)
            .enter()
            .append("rect")
            .attr("class", "heatmap-rect")
            .attr("x", d => xScale(d.file_path))
            .attr("y", d => yScale(d.author))
            .attr("width", xScale.bandwidth())
            .attr("height", yScale.bandwidth())
            .style("fill", d => colorScale(d.percentage))
            .style("stroke", "white")
            .style("stroke-width", 1)
            .append("title")
            .text(d => `${d.author}: ${d.file_path} (${d.percentage}%)`);

        // Add axes
        svg.append("g")
            .attr("transform", `translate(0,${height})`)
            .call(d3.axisBottom(xScale))
            .selectAll("text")
            .style("text-anchor", "end")
            .attr("dx", "-.8em")
            .attr("dy", ".15em")
            .attr("transform", "rotate(-45)");

        svg.append("g")
            .call(d3.axisLeft(yScale));

        // Add title
        svg.append("text")
            .attr("x", width / 2)
            .attr("y", -20)
            .attr("text-anchor", "middle")
            .style("font-size", "16px")
            .style("font-weight", "bold")
            .text("Code Ownership Heatmap");
    }

    /**
     * Create simple HTML heatmap fallback
     */
    createSimpleHeatmap(container, heatmapData) {
        let html = '<div class="simple-heatmap">';
        html += '<h4>Code Ownership by Directory</h4>';

        heatmapData.slice(0, 5).forEach(dir => {
            html += `<div class="directory-section">`;
            html += `<h5>${dir.directory}</h5>`;
            html += `<div class="files-grid">`;

            dir.files.slice(0, 10).forEach(file => {
                const intensity = Math.min(file.percentage / 100, 1);
                const color = `rgba(37, 99, 235, ${intensity})`;
                
                html += `<div class="file-item" style="background-color: ${color};" title="${file.author}: ${file.file_path} (${file.percentage}%)">`;
                html += `<span class="file-name">${file.file_path.split('/').pop()}</span>`;
                html += `<span class="file-owner">${file.author}</span>`;
                html += `<span class="file-percentage">${file.percentage}%</span>`;
                html += `</div>`;
            });

            html += `</div></div>`;
        });

        html += '</div>';
        container.innerHTML = html;
    }

    /**
     * Load activity visualization
     */
    async loadActivityVisualization() {
        const data = await api.getActivityData(this.repositoryId, 'daily');
        
        this.hideAllContainers();
        this.showContainer('main-chart');

        const ctx = document.getElementById('main-chart');
        if (!ctx) return;

        // Destroy any existing chart on the main canvas
        this.destroyMainCanvasChart();

        const chartData = {
            labels: data.activity_data.map(point => point.day || point.hour),
            datasets: [{
                label: 'Commits',
                data: data.activity_data.map(point => point.commits),
                backgroundColor: CONFIG.CHARTS.DEFAULT_COLORS[0],
                borderColor: CONFIG.CHARTS.DEFAULT_COLORS[0],
                borderWidth: 1
            }]
        };

        this.charts.activity = new Chart(ctx, {
            type: 'bar',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Number of Commits'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: `Activity Patterns (${data.type})`
                    },
                    legend: {
                        display: false
                    }
                }
            }
        });
    }

    /**
     * Load languages visualization
     */
    async loadLanguagesVisualization() {
        const data = await api.getLanguageDistribution(this.repositoryId);
        
        this.hideAllContainers();
        this.showContainer('main-chart');

        const ctx = document.getElementById('main-chart');
        if (!ctx) return;

        // Destroy any existing chart on the main canvas
        this.destroyMainCanvasChart();

        const chartData = {
            labels: data.languages.map(lang => lang.language),
            datasets: [{
                label: 'Lines of Code',
                data: data.languages.map(lang => lang.lines),
                backgroundColor: CONFIG.CHARTS.DEFAULT_COLORS,
                borderWidth: 1
            }]
        };

        this.charts.languages = new Chart(ctx, {
            type: 'doughnut',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Programming Languages Distribution'
                    },
                    legend: {
                        position: 'right'
                    }
                }
            }
        });
    }

    /**
     * Show loading state
     */
    showLoading(show) {
        const loadingElement = document.getElementById('viz-loading');
        if (loadingElement) {
            if (show) {
                loadingElement.classList.remove('hidden');
            } else {
                loadingElement.classList.add('hidden');
            }
        }
    }

    /**
     * Show error message
     */
    showError(message) {
        const container = document.getElementById('visualization-container');
        if (container) {
            this.hideAllContainers();
            container.innerHTML = `
                <div class="viz-error">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>${message}</p>
                    <button onclick="window.visualizationManager.switchVisualization('${this.currentVisualization}')" class="btn btn-sm btn-primary">
                        <i class="fas fa-redo"></i> Retry
                    </button>
                </div>
            `;
        }
    }

    /**
     * Hide all visualization containers
     */
    hideAllContainers() {
        const containers = ['main-chart', 'heatmap-container', 'network-container'];
        containers.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.classList.add('hidden');
            }
        });
    }

    /**
     * Show specific container
     */
    showContainer(containerId) {
        const element = document.getElementById(containerId);
        if (element) {
            element.classList.remove('hidden');
        }
    }

    /**
     * Destroy any existing chart on the main canvas
     */
    destroyMainCanvasChart() {
        // Find and destroy any chart that might be using the main-chart canvas
        const chartTypes = ['timeline', 'contributors', 'activity', 'languages'];
        
        chartTypes.forEach(type => {
            if (this.charts[type]) {
                this.charts[type].destroy();
                delete this.charts[type];
            }
        });
        
        // Also check for any Chart.js instances attached to the canvas
        const ctx = document.getElementById('main-chart');
        if (ctx && ctx.chart) {
            ctx.chart.destroy();
        }
    }

    /**
     * Destroy all charts
     */
    destroy() {
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        this.charts = {};
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VisualizationManager;
}

// Make VisualizationManager available globally
window.VisualizationManager = VisualizationManager;
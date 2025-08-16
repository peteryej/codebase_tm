/**
 * Main Application Controller for Codebase Time Machine
 */

class CodebaseTimeMachine {
    constructor() {
        this.currentRepository = null;
        this.analysisPollingInterval = null;
        this.theme = localStorage.getItem(CONFIG.STORAGE_KEYS.THEME) || 'light';
        
        this.init();
    }

    /**
     * Initialize the application
     */
    init() {
        this.setupEventListeners();
        this.setupTheme();
        this.loadRecentRepositories();
        this.showSection('repo-input-section');
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Repository input
        const repoInput = document.getElementById('repo-url');
        const analyzeBtn = document.getElementById('analyze-btn');
        const retryBtn = document.getElementById('retry-btn');
        const themeToggle = document.getElementById('theme-toggle');

        if (repoInput) {
            repoInput.addEventListener('input', this.debounce(this.validateRepositoryUrl.bind(this), 300));
            repoInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.startAnalysis();
                }
            });
        }

        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', this.startAnalysis.bind(this));
        }

        if (retryBtn) {
            retryBtn.addEventListener('click', this.resetToInput.bind(this));
        }

        if (themeToggle) {
            themeToggle.addEventListener('click', this.toggleTheme.bind(this));
        }

        // Suggested queries click handlers
        document.addEventListener('click', (e) => {
            if (e.target.closest('.welcome-message li')) {
                const query = e.target.textContent.replace(/['"]/g, '');
                if (window.chatInterface) {
                    window.chatInterface.sendMessage(query);
                }
            }
        });

        // Recent repositories click handlers
        document.addEventListener('click', (e) => {
            if (e.target.closest('.recent-repo-item')) {
                const repoUrl = e.target.closest('.recent-repo-item').dataset.url;
                if (repoUrl) {
                    document.getElementById('repo-url').value = repoUrl;
                    this.startAnalysis();
                }
            }
        });
    }

    /**
     * Setup theme
     */
    setupTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
        this.updateThemeIcon();
    }

    /**
     * Toggle theme
     */
    toggleTheme() {
        this.theme = this.theme === 'light' ? 'dark' : 'light';
        localStorage.setItem(CONFIG.STORAGE_KEYS.THEME, this.theme);
        this.setupTheme();
    }

    /**
     * Update theme icon
     */
    updateThemeIcon() {
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            const icon = themeToggle.querySelector('i');
            if (icon) {
                icon.className = this.theme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
            }
        }
    }

    /**
     * Validate repository URL
     */
    async validateRepositoryUrl() {
        const input = document.getElementById('repo-url');
        const message = document.getElementById('validation-message');
        const analyzeBtn = document.getElementById('analyze-btn');

        if (!input || !message || !analyzeBtn) return;

        const url = input.value.trim();
        
        // Clear previous messages
        message.className = 'message hidden';
        message.textContent = '';

        if (!url) {
            analyzeBtn.disabled = true;
            return;
        }

        // Basic URL validation
        if (!APIUtils.isValidGitHubUrl(url)) {
            this.showMessage(message, CONFIG.ERRORS.VALIDATION, 'error');
            analyzeBtn.disabled = true;
            return;
        }

        try {
            // Validate with API
            const result = await api.validateRepository(APIUtils.formatRepositoryUrl(url));
            
            if (result.valid) {
                this.showMessage(message, CONFIG.SUCCESS.VALIDATION_SUCCESS, 'success');
                analyzeBtn.disabled = false;
            } else {
                this.showMessage(message, result.error || CONFIG.ERRORS.VALIDATION, 'error');
                analyzeBtn.disabled = true;
            }
        } catch (error) {
            const errorMessage = APIUtils.handleError(error, 'validation');
            this.showMessage(message, errorMessage, 'error');
            analyzeBtn.disabled = true;
        }
    }

    /**
     * Start repository analysis
     */
    async startAnalysis() {
        const input = document.getElementById('repo-url');
        const url = input?.value.trim();

        if (!url) {
            this.showError('Please enter a repository URL');
            return;
        }

        if (!APIUtils.isValidGitHubUrl(url)) {
            this.showError(CONFIG.ERRORS.VALIDATION);
            return;
        }

        try {
            this.showLoadingOverlay(true);
            
            const formattedUrl = APIUtils.formatRepositoryUrl(url);
            const result = await api.analyzeRepository(formattedUrl);

            if (result.repository_id) {
                this.currentRepository = {
                    id: result.repository_id,
                    url: formattedUrl,
                    analysisId: result.analysis_id
                };

                // Save to recent repositories
                this.saveRecentRepository(formattedUrl);

                // Show progress section
                this.showSection('analysis-progress-section');
                this.startAnalysisPolling();
            } else {
                throw new Error(result.error || 'Failed to start analysis');
            }
        } catch (error) {
            const errorMessage = APIUtils.handleError(error, 'analysis start');
            this.showError(errorMessage);
        } finally {
            this.showLoadingOverlay(false);
        }
    }

    /**
     * Start polling for analysis status
     */
    startAnalysisPolling() {
        if (!this.currentRepository) return;

        this.analysisPollingInterval = setInterval(async () => {
            try {
                const status = await api.getAnalysisStatus(this.currentRepository.id);
                this.updateAnalysisProgress(status);

                if (status.status === 'completed') {
                    this.stopAnalysisPolling();
                    await this.loadDashboard();
                } else if (status.status === 'error') {
                    this.stopAnalysisPolling();
                    this.showError(status.error_message || CONFIG.ERRORS.ANALYSIS_FAILED);
                }
            } catch (error) {
                console.error('Error polling analysis status:', error);
                // Continue polling unless it's a critical error
                if (error instanceof APIError && error.isClientError()) {
                    this.stopAnalysisPolling();
                    this.showError(APIUtils.handleError(error, 'analysis polling'));
                }
            }
        }, CONFIG.UI.ANALYSIS_POLL_INTERVAL);

        // Set timeout to stop polling after maximum time
        setTimeout(() => {
            if (this.analysisPollingInterval) {
                this.stopAnalysisPolling();
                this.showError(CONFIG.ERRORS.ANALYSIS_TIMEOUT);
            }
        }, CONFIG.UI.ANALYSIS_TIMEOUT);
    }

    /**
     * Stop analysis polling
     */
    stopAnalysisPolling() {
        if (this.analysisPollingInterval) {
            clearInterval(this.analysisPollingInterval);
            this.analysisPollingInterval = null;
        }
    }

    /**
     * Update analysis progress
     */
    updateAnalysisProgress(status) {
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        const steps = document.querySelectorAll('.step');

        if (progressFill && status.progress !== undefined) {
            progressFill.style.width = `${status.progress}%`;
        }

        if (progressText && status.current_step) {
            progressText.textContent = status.current_step;
        }

        // Update step indicators
        steps.forEach(step => {
            step.classList.remove('active', 'completed');
        });

        if (status.current_step) {
            const currentStep = this.getStepFromMessage(status.current_step);
            const stepElement = document.querySelector(`[data-step="${currentStep}"]`);
            
            if (stepElement) {
                stepElement.classList.add('active');
                
                // Mark previous steps as completed
                const stepOrder = ['clone', 'commits', 'ownership', 'complete'];
                const currentIndex = stepOrder.indexOf(currentStep);
                
                for (let i = 0; i < currentIndex; i++) {
                    const prevStep = document.querySelector(`[data-step="${stepOrder[i]}"]`);
                    if (prevStep) {
                        prevStep.classList.remove('active');
                        prevStep.classList.add('completed');
                    }
                }
            }
        }
    }

    /**
     * Get step identifier from status message
     */
    getStepFromMessage(message) {
        const lowerMessage = message.toLowerCase();
        
        if (lowerMessage.includes('clone') || lowerMessage.includes('cloning')) {
            return 'clone';
        } else if (lowerMessage.includes('commit') || lowerMessage.includes('analyzing commits')) {
            return 'commits';
        } else if (lowerMessage.includes('ownership') || lowerMessage.includes('analyzing code ownership')) {
            return 'ownership';
        } else if (lowerMessage.includes('completed') || lowerMessage.includes('complete')) {
            return 'complete';
        }
        
        return 'clone'; // Default
    }

    /**
     * Load dashboard after successful analysis
     */
    async loadDashboard() {
        if (!this.currentRepository) return;

        try {
            this.showLoadingOverlay(true);

            // Load repository data
            const [authorsData, ownershipData] = await Promise.all([
                api.getAuthorStatistics(this.currentRepository.id),
                api.getOwnershipOverview(this.currentRepository.id)
            ]);

            // Update repository header
            this.updateRepositoryHeader(authorsData, ownershipData);

            // Initialize chat interface
            if (window.ChatInterface) {
                window.chatInterface = new ChatInterface(this.currentRepository.id);
            }

            // Initialize visualizations
            if (window.VisualizationManager) {
                window.visualizationManager = new VisualizationManager(this.currentRepository.id);
                await window.visualizationManager.loadInitialVisualization();
            }

            // Load additional info panels
            this.loadInfoPanels(authorsData, ownershipData);

            // Show dashboard
            this.showSection('dashboard-section');

        } catch (error) {
            console.error('Error loading dashboard:', error);
            this.showError(APIUtils.handleError(error, 'dashboard loading'));
        } finally {
            this.showLoadingOverlay(false);
        }
    }

    /**
     * Update repository header with basic info
     */
    updateRepositoryHeader(authorsData, ownershipData) {
        const repoName = document.getElementById('repo-name');
        const repoDescription = document.getElementById('repo-description');
        const totalCommits = document.getElementById('total-commits');
        const totalFiles = document.getElementById('total-files');
        const totalContributors = document.getElementById('total-contributors');

        if (this.currentRepository && repoName) {
            const parsed = APIUtils.parseGitHubUrl(this.currentRepository.url);
            if (parsed) {
                repoName.textContent = `${parsed.owner}/${parsed.repo}`;
            }
        }

        if (authorsData && authorsData.authors) {
            const totalCommitsCount = authorsData.authors.reduce((sum, author) => sum + author.commits, 0);
            if (totalCommits) totalCommits.textContent = totalCommitsCount.toLocaleString();
            if (totalContributors) totalContributors.textContent = authorsData.authors.length.toLocaleString();
        }

        if (ownershipData && ownershipData.ownership) {
            if (totalFiles) totalFiles.textContent = ownershipData.ownership.total_files?.toLocaleString() || '0';
        }
    }

    /**
     * Load info panels
     */
    loadInfoPanels(authorsData, ownershipData) {
        this.loadTopContributors(authorsData);
        this.loadLanguageBreakdown(ownershipData);
        this.loadRecentActivity();
    }

    /**
     * Load top contributors panel
     */
    loadTopContributors(authorsData) {
        const container = document.getElementById('top-contributors');
        if (!container || !authorsData?.authors) return;

        container.innerHTML = '';

        authorsData.authors.slice(0, 5).forEach(author => {
            const item = document.createElement('div');
            item.className = 'contributor-item';
            item.innerHTML = `
                <div>
                    <div class="contributor-name">${this.escapeHtml(author.name)}</div>
                    <div class="contributor-stats">${author.commits} commits (${author.percentage}%)</div>
                </div>
            `;
            container.appendChild(item);
        });
    }

    /**
     * Load language breakdown panel
     */
    loadLanguageBreakdown(ownershipData) {
        const container = document.getElementById('language-breakdown');
        if (!container || !ownershipData?.ownership?.extension_breakdown) return;

        container.innerHTML = '';

        ownershipData.ownership.extension_breakdown.slice(0, 5).forEach(ext => {
            const item = document.createElement('div');
            item.className = 'language-item';
            
            const language = ext.extension === 'no_extension' ? 'Other' : ext.extension.toUpperCase();
            const percentage = Math.round((ext.files / ownershipData.ownership.total_files) * 100);
            
            item.innerHTML = `
                <span class="language-name">${this.escapeHtml(language)}</span>
                <span class="language-percentage">${ext.files} files (${percentage}%)</span>
            `;
            container.appendChild(item);
        });
    }

    /**
     * Load recent activity panel
     */
    async loadRecentActivity() {
        const container = document.getElementById('recent-activity');
        if (!container || !this.currentRepository) return;

        try {
            const timelineData = await api.getCommitTimeline(this.currentRepository.id, 7); // Last 7 days
            
            container.innerHTML = '';

            if (timelineData.timeline && timelineData.timeline.length > 0) {
                const recentDays = timelineData.timeline.slice(-7);
                
                recentDays.forEach(day => {
                    if (day.commits > 0) {
                        const item = document.createElement('div');
                        item.className = 'activity-item';
                        item.innerHTML = `
                            <div class="activity-date">${new Date(day.date).toLocaleDateString()}</div>
                            <div class="activity-description">${day.commits} commit${day.commits !== 1 ? 's' : ''}</div>
                        `;
                        container.appendChild(item);
                    }
                });

                if (container.children.length === 0) {
                    container.innerHTML = '<p>No recent activity</p>';
                }
            } else {
                container.innerHTML = '<p>No recent activity</p>';
            }
        } catch (error) {
            console.error('Error loading recent activity:', error);
            container.innerHTML = '<p>Failed to load recent activity</p>';
        }
    }

    /**
     * Show specific section and hide others
     */
    showSection(sectionId) {
        const sections = ['repo-input-section', 'analysis-progress-section', 'dashboard-section', 'error-section'];
        
        sections.forEach(id => {
            const section = document.getElementById(id);
            if (section) {
                if (id === sectionId) {
                    section.classList.remove('hidden');
                    section.classList.add('fade-in');
                } else {
                    section.classList.add('hidden');
                    section.classList.remove('fade-in');
                }
            }
        });
    }

    /**
     * Show error message
     */
    showError(message) {
        const errorSection = document.getElementById('error-section');
        const errorMessage = document.getElementById('error-message');

        if (errorMessage) {
            errorMessage.textContent = message;
        }

        this.showSection('error-section');
    }

    /**
     * Reset to input section
     */
    resetToInput() {
        this.stopAnalysisPolling();
        this.currentRepository = null;
        
        // Clear input
        const input = document.getElementById('repo-url');
        if (input) {
            input.value = '';
        }

        // Clear validation message
        const message = document.getElementById('validation-message');
        if (message) {
            message.className = 'message hidden';
        }

        this.showSection('repo-input-section');
    }

    /**
     * Show/hide loading overlay
     */
    showLoadingOverlay(show) {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            if (show) {
                overlay.classList.remove('hidden');
            } else {
                overlay.classList.add('hidden');
            }
        }
    }

    /**
     * Show message in element
     */
    showMessage(element, message, type) {
        if (!element) return;
        
        element.textContent = message;
        element.className = `message ${type}`;
    }

    /**
     * Load recent repositories from localStorage
     */
    loadRecentRepositories() {
        try {
            const recent = JSON.parse(localStorage.getItem(CONFIG.STORAGE_KEYS.RECENT_REPOS) || '[]');
            const container = document.getElementById('recent-repos-list');
            const section = document.getElementById('recent-repos');

            if (!container || !section || recent.length === 0) return;

            container.innerHTML = '';

            recent.slice(0, CONFIG.LIMITS.MAX_RECENT_REPOS).forEach(repo => {
                const item = document.createElement('div');
                item.className = 'recent-repo-item';
                item.dataset.url = repo.url;
                
                const parsed = APIUtils.parseGitHubUrl(repo.url);
                const displayName = parsed ? `${parsed.owner}/${parsed.repo}` : repo.url;
                
                item.innerHTML = `
                    <span class="recent-repo-name">${this.escapeHtml(displayName)}</span>
                    <span class="recent-repo-date">${new Date(repo.date).toLocaleDateString()}</span>
                `;
                container.appendChild(item);
            });

            section.classList.remove('hidden');
        } catch (error) {
            console.error('Error loading recent repositories:', error);
        }
    }

    /**
     * Save repository to recent list
     */
    saveRecentRepository(url) {
        try {
            let recent = JSON.parse(localStorage.getItem(CONFIG.STORAGE_KEYS.RECENT_REPOS) || '[]');
            
            // Remove if already exists
            recent = recent.filter(repo => repo.url !== url);
            
            // Add to beginning
            recent.unshift({
                url,
                date: new Date().toISOString()
            });

            // Keep only the most recent
            recent = recent.slice(0, CONFIG.LIMITS.MAX_RECENT_REPOS);

            localStorage.setItem(CONFIG.STORAGE_KEYS.RECENT_REPOS, JSON.stringify(recent));
        } catch (error) {
            console.error('Error saving recent repository:', error);
        }
    }

    /**
     * Debounce utility
     */
    debounce(func, delay) {
        let timeoutId;
        return function (...args) {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func.apply(this, args), delay);
        };
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new CodebaseTimeMachine();
});
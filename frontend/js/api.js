/**
 * API Client for Codebase Time Machine
 */

class APIClient {
    constructor() {
        this.baseURL = CONFIG.API_BASE_URL;
        this.defaultHeaders = {
            'Content-Type': 'application/json',
        };
    }

    /**
     * Make HTTP request with error handling
     */
    async request(endpoint, options = {}) {
        const url = endpoint.startsWith('http') ? endpoint : `${this.baseURL}${endpoint}`;
        
        const config = {
            headers: { ...this.defaultHeaders, ...options.headers },
            ...options
        };

        try {
            const response = await fetch(url, config);
            
            // Handle different response types
            const contentType = response.headers.get('content-type');
            let data;
            
            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                data = await response.text();
            }

            if (!response.ok) {
                throw new APIError(
                    data.error || `HTTP ${response.status}`,
                    response.status,
                    data
                );
            }

            return data;
        } catch (error) {
            if (error instanceof APIError) {
                throw error;
            }
            
            // Network or other errors
            throw new APIError(
                error.message || CONFIG.ERRORS.NETWORK,
                0,
                { originalError: error }
            );
        }
    }

    /**
     * GET request
     */
    async get(endpoint, params = {}) {
        const url = new URL(endpoint.startsWith('http') ? endpoint : `${this.baseURL}${endpoint}`);
        
        // Add query parameters
        Object.keys(params).forEach(key => {
            if (params[key] !== undefined && params[key] !== null) {
                url.searchParams.append(key, params[key]);
            }
        });

        return this.request(url.toString(), { method: 'GET' });
    }

    /**
     * POST request
     */
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * PUT request
     */
    async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    /**
     * DELETE request
     */
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    // Repository API methods
    async validateRepository(url) {
        return this.post(CONFIG.ENDPOINTS.REPOSITORY.VALIDATE, { url });
    }

    async analyzeRepository(url, forceRefresh = false) {
        return this.post(CONFIG.ENDPOINTS.REPOSITORY.ANALYZE, { 
            url, 
            force_refresh: forceRefresh 
        });
    }

    async getAnalysisStatus(repositoryId) {
        const endpoint = CONFIG.ENDPOINTS.REPOSITORY.STATUS.replace('{id}', repositoryId);
        return this.get(endpoint);
    }

    async listRepositories() {
        return this.get(CONFIG.ENDPOINTS.REPOSITORY.LIST);
    }

    async getCommitTimeline(repositoryId, days = 365) {
        const endpoint = CONFIG.ENDPOINTS.REPOSITORY.TIMELINE.replace('{id}', repositoryId);
        return this.get(endpoint, { days });
    }

    async getAuthorStatistics(repositoryId) {
        const endpoint = CONFIG.ENDPOINTS.REPOSITORY.AUTHORS.replace('{id}', repositoryId);
        return this.get(endpoint);
    }

    async getOwnershipOverview(repositoryId) {
        const endpoint = CONFIG.ENDPOINTS.REPOSITORY.OWNERSHIP.replace('{id}', repositoryId);
        return this.get(endpoint);
    }

    async getFileOwnership(repositoryId, filePath) {
        const endpoint = CONFIG.ENDPOINTS.REPOSITORY.OWNERSHIP_FILE.replace('{id}', repositoryId);
        return this.get(endpoint, { path: filePath });
    }

    async getOwnershipHeatmap(repositoryId, minPercentage = 5, maxFiles = 100) {
        const endpoint = CONFIG.ENDPOINTS.REPOSITORY.OWNERSHIP_HEATMAP.replace('{id}', repositoryId);
        return this.get(endpoint, { min_percentage: minPercentage, max_files: maxFiles });
    }

    async getCodeExperts(repositoryId, extension = null) {
        const endpoint = CONFIG.ENDPOINTS.REPOSITORY.EXPERTS.replace('{id}', repositoryId);
        const params = extension ? { extension } : {};
        return this.get(endpoint, params);
    }

    async getRepositoryFeatures(repositoryId) {
        const endpoint = CONFIG.ENDPOINTS.REPOSITORY.FEATURES.replace('{id}', repositoryId);
        return this.get(endpoint);
    }

    // Chat API methods
    async sendChatQuery(repositoryId, query, useCache = true) {
        return this.post(CONFIG.ENDPOINTS.CHAT.QUERY, {
            repository_id: repositoryId,
            query,
            use_cache: useCache
        });
    }

    async getChatSuggestions(repositoryId) {
        return this.get(CONFIG.ENDPOINTS.CHAT.SUGGESTIONS, { repository_id: repositoryId });
    }

    async getChatHistory(repositoryId, limit = 10) {
        return this.get(CONFIG.ENDPOINTS.CHAT.HISTORY, { 
            repository_id: repositoryId, 
            limit 
        });
    }

    // Visualization API methods
    async getTimelineData(repositoryId, days = 365, granularity = 'daily') {
        const endpoint = CONFIG.ENDPOINTS.VISUALIZATION.TIMELINE.replace('{id}', repositoryId);
        return this.get(endpoint, { days, granularity });
    }

    async getHeatmapData(repositoryId, minPercentage = 5, maxFiles = 100) {
        const endpoint = CONFIG.ENDPOINTS.VISUALIZATION.HEATMAP.replace('{id}', repositoryId);
        return this.get(endpoint, { min_percentage: minPercentage, max_files: maxFiles });
    }

    async getContributorsData(repositoryId, topN = 10, metric = 'commits') {
        const endpoint = CONFIG.ENDPOINTS.VISUALIZATION.CONTRIBUTORS.replace('{id}', repositoryId);
        return this.get(endpoint, { top_n: topN, metric });
    }

    async getActivityData(repositoryId, type = 'daily') {
        const endpoint = CONFIG.ENDPOINTS.VISUALIZATION.ACTIVITY.replace('{id}', repositoryId);
        return this.get(endpoint, { type });
    }

    async getLanguageDistribution(repositoryId) {
        const endpoint = CONFIG.ENDPOINTS.VISUALIZATION.LANGUAGES.replace('{id}', repositoryId);
        return this.get(endpoint);
    }

    async getCollaborationData(repositoryId) {
        const endpoint = CONFIG.ENDPOINTS.VISUALIZATION.COLLABORATION.replace('{id}', repositoryId);
        return this.get(endpoint);
    }
}

/**
 * Custom API Error class
 */
class APIError extends Error {
    constructor(message, status = 0, data = null) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.data = data;
    }

    isNetworkError() {
        return this.status === 0;
    }

    isClientError() {
        return this.status >= 400 && this.status < 500;
    }

    isServerError() {
        return this.status >= 500;
    }
}

/**
 * Utility functions for API handling
 */
const APIUtils = {
    /**
     * Handle API errors with user-friendly messages
     */
    handleError(error, context = '') {
        console.error(`API Error ${context}:`, error);

        let message = CONFIG.ERRORS.GENERIC;

        if (error instanceof APIError) {
            if (error.isNetworkError()) {
                message = CONFIG.ERRORS.NETWORK;
            } else if (error.status === 404) {
                message = 'Resource not found.';
            } else if (error.status === 429) {
                message = 'Too many requests. Please wait a moment and try again.';
            } else if (error.data && error.data.error) {
                message = error.data.error;
            } else {
                message = error.message;
            }
        } else if (error.message) {
            message = error.message;
        }

        return message;
    },

    /**
     * Retry API call with exponential backoff
     */
    async retryWithBackoff(apiCall, maxRetries = 3, baseDelay = 1000) {
        let lastError;

        for (let attempt = 0; attempt < maxRetries; attempt++) {
            try {
                return await apiCall();
            } catch (error) {
                lastError = error;

                // Don't retry client errors (4xx)
                if (error instanceof APIError && error.isClientError()) {
                    throw error;
                }

                // Wait before retrying (exponential backoff)
                if (attempt < maxRetries - 1) {
                    const delay = baseDelay * Math.pow(2, attempt);
                    await new Promise(resolve => setTimeout(resolve, delay));
                }
            }
        }

        throw lastError;
    },

    /**
     * Debounce function for API calls
     */
    debounce(func, delay = CONFIG.UI.DEBOUNCE_DELAY) {
        let timeoutId;
        return function (...args) {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func.apply(this, args), delay);
        };
    },

    /**
     * Format repository URL for validation
     */
    formatRepositoryUrl(url) {
        if (!url) return '';
        
        url = url.trim();
        
        // Add https:// if missing
        if (!url.startsWith('http')) {
            url = 'https://' + url;
        }
        
        // Remove trailing slash
        url = url.replace(/\/$/, '');
        
        // Remove .git suffix
        url = url.replace(/\.git$/, '');
        
        return url;
    },

    /**
     * Validate GitHub repository URL
     */
    isValidGitHubUrl(url) {
        if (!url) return false;
        
        const formattedUrl = this.formatRepositoryUrl(url);
        return CONFIG.REGEX.GITHUB_URL.test(formattedUrl);
    },

    /**
     * Extract owner and repo name from GitHub URL
     */
    parseGitHubUrl(url) {
        const match = url.match(CONFIG.REGEX.GITHUB_URL_FLEXIBLE);
        if (match) {
            return {
                owner: match[1],
                repo: match[2]
            };
        }
        return null;
    }
};

// Create global API client instance
const api = new APIClient();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { APIClient, APIError, APIUtils, api };
}
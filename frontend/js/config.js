/**
 * Configuration for Codebase Time Machine Frontend
 */

const CONFIG = {
    // API Configuration
    API_BASE_URL: 'http://localhost:5000/api',
    
    // Endpoints
    ENDPOINTS: {
        REPOSITORY: {
            VALIDATE: '/repository/validate',
            ANALYZE: '/repository/analyze',
            STATUS: '/repository/{id}/status',
            LIST: '/repository/list',
            TIMELINE: '/repository/{id}/timeline',
            AUTHORS: '/repository/{id}/authors',
            OWNERSHIP: '/repository/{id}/ownership',
            OWNERSHIP_FILE: '/repository/{id}/ownership/file',
            OWNERSHIP_HEATMAP: '/repository/{id}/ownership/heatmap',
            EXPERTS: '/repository/{id}/experts',
            FEATURES: '/repository/{id}/features'
        },
        CHAT: {
            QUERY: '/chat/query',
            SUGGESTIONS: '/chat/suggestions',
            HISTORY: '/chat/history'
        },
        VISUALIZATION: {
            TIMELINE: '/visualization/{id}/timeline',
            HEATMAP: '/visualization/{id}/heatmap',
            CONTRIBUTORS: '/visualization/{id}/contributors',
            ACTIVITY: '/visualization/{id}/activity',
            LANGUAGES: '/visualization/{id}/languages',
            COLLABORATION: '/visualization/{id}/collaboration'
        }
    },
    
    // UI Configuration
    UI: {
        ANALYSIS_POLL_INTERVAL: 2000, // 2 seconds
        ANALYSIS_TIMEOUT: 600000, // 10 minutes
        CHAT_MAX_MESSAGES: 50,
        VISUALIZATION_REFRESH_INTERVAL: 30000, // 30 seconds
        DEBOUNCE_DELAY: 300 // 300ms
    },
    
    // Chart Configuration
    CHARTS: {
        DEFAULT_COLORS: [
            '#2563eb', '#dc2626', '#16a34a', '#ca8a04', '#9333ea',
            '#c2410c', '#0891b2', '#be123c', '#4338ca', '#059669'
        ],
        TIMELINE: {
            BACKGROUND_COLOR: 'rgba(37, 99, 235, 0.1)',
            BORDER_COLOR: '#2563eb',
            POINT_BACKGROUND_COLOR: '#2563eb',
            POINT_BORDER_COLOR: '#ffffff'
        },
        CONTRIBUTORS: {
            BACKGROUND_COLORS: [
                'rgba(37, 99, 235, 0.8)',
                'rgba(220, 38, 38, 0.8)',
                'rgba(22, 163, 74, 0.8)',
                'rgba(202, 138, 4, 0.8)',
                'rgba(147, 51, 234, 0.8)'
            ]
        }
    },
    
    // Local Storage Keys
    STORAGE_KEYS: {
        THEME: 'ctm_theme',
        RECENT_REPOS: 'ctm_recent_repos',
        CHAT_HISTORY: 'ctm_chat_history',
        USER_PREFERENCES: 'ctm_preferences'
    },
    
    // Error Messages
    ERRORS: {
        NETWORK: 'Network error. Please check your connection and try again.',
        VALIDATION: 'Please enter a valid GitHub repository URL.',
        ANALYSIS_FAILED: 'Repository analysis failed. Please try again.',
        ANALYSIS_TIMEOUT: 'Analysis is taking longer than expected. Please check back later.',
        CHAT_FAILED: 'Failed to process your question. Please try again.',
        VISUALIZATION_FAILED: 'Failed to load visualization. Please try again.',
        GENERIC: 'Something went wrong. Please try again.'
    },
    
    // Success Messages
    SUCCESS: {
        ANALYSIS_STARTED: 'Analysis started successfully!',
        ANALYSIS_COMPLETED: 'Repository analysis completed!',
        VALIDATION_SUCCESS: 'Repository validated successfully!'
    },
    
    // Regular Expressions
    REGEX: {
        GITHUB_URL: /^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+\/?$/,
        GITHUB_URL_FLEXIBLE: /github\.com\/([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+)/
    },
    
    // Animation Durations
    ANIMATIONS: {
        FADE_DURATION: 300,
        SLIDE_DURATION: 250,
        CHART_ANIMATION_DURATION: 1000
    },
    
    // Limits
    LIMITS: {
        MAX_REPO_URL_LENGTH: 200,
        MAX_CHAT_MESSAGE_LENGTH: 500,
        MAX_RECENT_REPOS: 10,
        MAX_VISUALIZATION_DATA_POINTS: 100
    }
};

// Utility function to replace URL parameters
CONFIG.getEndpoint = function(endpoint, params = {}) {
    let url = this.API_BASE_URL + endpoint;
    
    // Replace URL parameters
    Object.keys(params).forEach(key => {
        url = url.replace(`{${key}}`, params[key]);
    });
    
    return url;
};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CONFIG;
}
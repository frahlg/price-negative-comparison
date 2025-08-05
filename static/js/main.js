/**
 * Sourceful Energy - Main JavaScript functionality
 * Handles interactive features for the web interface
 */

class SourcefulEnergy {
    constructor() {
        this.apiBase = '/api';
        this.init();
    }

    init() {
        console.log('🚀 Sourceful Energy - Accelerating smart energy flows');
        this.checkApiHealth();
        this.setupEventListeners();
    }

    /**
     * Check API health status and update UI
     */
    async checkApiHealth() {
        try {
            const response = await fetch(`${this.apiBase}/health`);
            const data = await response.json();
            
            const statusElement = document.getElementById('api-status');
            if (statusElement) {
                if (data.status === 'healthy') {
                    statusElement.textContent = '● Online';
                    statusElement.className = 'text-success';
                } else {
                    statusElement.textContent = '● Issues';
                    statusElement.className = 'text-warning';
                }
            }
        } catch (error) {
            console.error('API health check failed:', error);
            const statusElement = document.getElementById('api-status');
            if (statusElement) {
                statusElement.textContent = '● Offline';
                statusElement.className = 'text-danger';
            }
        }
    }

    /**
     * Setup event listeners for interactive elements
     */
    setupEventListeners() {
        // Future: File upload handlers
        // Future: Form submission handlers
        // Future: Real-time updates
        
        // Example: Console log for demonstration
        document.addEventListener('DOMContentLoaded', () => {
            console.log('DOM ready - Sourceful Energy initialized');
        });
    }

    /**
     * Utility function for API calls
     */
    async apiCall(endpoint, options = {}) {
        try {
            const response = await fetch(`${this.apiBase}${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`API call failed: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API call error:', error);
            throw error;
        }
    }

    /**
     * Future: File upload with progress tracking
     */
    async uploadFile(file, endpoint, progressCallback) {
        const formData = new FormData();
        formData.append('file', file);

        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable && progressCallback) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    progressCallback(percentComplete);
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    resolve(JSON.parse(xhr.responseText));
                } else {
                    reject(new Error(`Upload failed: ${xhr.status}`));
                }
            });

            xhr.addEventListener('error', () => {
                reject(new Error('Upload error'));
            });

            xhr.open('POST', `${this.apiBase}${endpoint}`);
            xhr.send(formData);
        });
    }

    /**
     * Utility: Show notification/alert
     */
    showNotification(message, type = 'info') {
        // Future: Implement toast notifications
        console.log(`[${type.toUpperCase()}] ${message}`);
    }

    /**
     * Utility: Format currency values
     */
    formatCurrency(value, currency = 'SEK') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 2,
            maximumFractionDigits: 4
        }).format(value);
    }

    /**
     * Utility: Format dates for API calls
     */
    formatDateForApi(date) {
        return date.toISOString().split('T')[0];
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.sourcefulEnergy = new SourcefulEnergy();
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SourcefulEnergy;
}

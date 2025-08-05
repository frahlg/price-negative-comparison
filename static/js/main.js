/**
 * Sourceful Energy - Main JavaScript functionality
 * Handles interactive features for the web interface
 */

class SourcefulEnergy {
    constructor() {
        this.apiBase = '/_api';  // Internal API prefix
        this.apiToken = null;
        this.apiHeader = null;
        this.init();
    }

    async init() {
        console.log('🚀 Sourceful Energy - Accelerating smart energy flows');
        await this.getApiToken();
        this.checkApiHealth();
        this.setupEventListeners();
        this.initAnimations();
    }

    /**
     * Get secure API token for internal API access
     */
    async getApiToken() {
        try {
            const response = await fetch('/api-token');
            const data = await response.json();
            this.apiToken = data.token;
            this.apiHeader = data.header;
        } catch (error) {
            console.error('Failed to get API token:', error);
        }
    }

    /**
     * Check API health status and update UI
     */
    async checkApiHealth() {
        try {
            const response = await this.apiCall('/health');
            
            // Update footer status indicators
            const statusIndicators = document.querySelectorAll('.status-indicator');
            statusIndicators.forEach(indicator => {
                if (response.status === 'healthy') {
                    indicator.classList.remove('bg-danger', 'bg-warning');
                    indicator.classList.add('bg-success');
                } else {
                    indicator.classList.remove('bg-success', 'bg-danger');
                    indicator.classList.add('bg-warning');
                }
            });
        } catch (error) {
            console.error('API health check failed:', error);
            const statusIndicators = document.querySelectorAll('.status-indicator');
            statusIndicators.forEach(indicator => {
                indicator.classList.remove('bg-success', 'bg-warning');
                indicator.classList.add('bg-danger');
            });
        }
    }

    /**
     * Setup event listeners for interactive elements
     */
    setupEventListeners() {
        // Enhanced upload area interactions
        const uploadPlaceholder = document.querySelector('.upload-placeholder');
        if (uploadPlaceholder) {
            uploadPlaceholder.addEventListener('dragover', this.handleDragOver.bind(this));
            uploadPlaceholder.addEventListener('dragleave', this.handleDragLeave.bind(this));
            uploadPlaceholder.addEventListener('drop', this.handleDrop.bind(this));
        }

        // Feature card hover enhancements
        const featureCards = document.querySelectorAll('.feature-card');
        featureCards.forEach(card => {
            card.addEventListener('mouseenter', this.enhanceCardHover.bind(this));
            card.addEventListener('mouseleave', this.resetCardHover.bind(this));
        });

        // Smooth scrolling for internal links
        document.querySelectorAll('a[href^="#"]').forEach(link => {
            link.addEventListener('click', this.smoothScroll.bind(this));
        });
    }

    /**
     * Initialize animations and visual enhancements
     */
    initAnimations() {
        // Add intersection observer for scroll animations
        if ('IntersectionObserver' in window) {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('animate-in');
                    }
                });
            }, { threshold: 0.1 });

            // Observe feature cards and upload section
            document.querySelectorAll('.feature-card, .upload-teaser').forEach(el => {
                el.classList.add('animate-on-scroll');
                observer.observe(el);
            });
        }

        // Add subtle parallax to hero section
        this.initParallax();
    }

    /**
     * Handle drag over event for upload area
     */
    handleDragOver(e) {
        e.preventDefault();
        e.currentTarget.style.borderColor = 'var(--sourceful-primary)';
        e.currentTarget.style.backgroundColor = 'rgba(0, 102, 204, 0.05)';
    }

    /**
     * Handle drag leave event for upload area
     */
    handleDragLeave(e) {
        e.preventDefault();
        e.currentTarget.style.borderColor = '#dee2e6';
        e.currentTarget.style.backgroundColor = '#f8f9fa';
    }

    /**
     * Handle drop event for upload area (placeholder for future functionality)
     */
    handleDrop(e) {
        e.preventDefault();
        this.handleDragLeave(e);
        
        // Future: Handle file upload
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            this.showComingSoonMessage();
        }
    }

    /**
     * Enhance card hover effect
     */
    enhanceCardHover(e) {
        const icon = e.currentTarget.querySelector('.feature-icon');
        if (icon) {
            icon.style.transform = 'scale(1.1) rotate(5deg)';
        }
    }

    /**
     * Reset card hover effect
     */
    resetCardHover(e) {
        const icon = e.currentTarget.querySelector('.feature-icon');
        if (icon) {
            icon.style.transform = 'scale(1) rotate(0deg)';
        }
    }

    /**
     * Smooth scrolling for anchor links
     */
    smoothScroll(e) {
        const href = e.currentTarget.getAttribute('href');
        if (href.startsWith('#')) {
            e.preventDefault();
            const target = document.querySelector(href);
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        }
    }

    /**
     * Initialize subtle parallax effect
     */
    initParallax() {
        const heroSection = document.querySelector('.hero-section');
        if (heroSection) {
            window.addEventListener('scroll', () => {
                const scrolled = window.pageYOffset;
                const rate = scrolled * -0.2;
                heroSection.style.transform = `translateY(${rate}px)`;
            });
        }
    }

    /**
     * Show coming soon message for upload functionality
     */
    showComingSoonMessage() {
        const button = document.querySelector('.upload-teaser .btn');
        if (button) {
            const originalText = button.innerHTML;
            button.innerHTML = '<i class="bi bi-info-circle me-2"></i>Coming Soon!';
            button.classList.add('btn-info');
            button.classList.remove('btn-primary');
            
            setTimeout(() => {
                button.innerHTML = originalText;
                button.classList.remove('btn-info');
                button.classList.add('btn-primary');
            }, 2000);
        }
    }

    /**
     * Utility function for secure API calls
     */
    async apiCall(endpoint, options = {}) {
        try {
            const headers = {
                'Content-Type': 'application/json',
                ...options.headers
            };
            
            // Add security token if available
            if (this.apiToken && this.apiHeader) {
                headers[this.apiHeader] = this.apiToken;
            }
            
            const response = await fetch(`${this.apiBase}${endpoint}`, {
                headers,
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
     * Secure file upload with progress tracking
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
            
            // Add security token
            if (this.apiToken && this.apiHeader) {
                xhr.setRequestHeader(this.apiHeader, this.apiToken);
            }
            
            xhr.send(formData);
        });
    }

    /**
     * Utility: Show notification/alert
     */
    showNotification(message, type = 'info') {
        // Create a simple toast notification
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} position-fixed top-0 end-0 m-3`;
        toast.style.zIndex = '9999';
        toast.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="bi bi-info-circle me-2"></i>
                ${message}
                <button type="button" class="btn-close ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 5000);
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

// Add CSS for scroll animations
const style = document.createElement('style');
style.textContent = `
    .animate-on-scroll {
        opacity: 0;
        transform: translateY(30px);
        transition: all 0.6s ease-out;
    }
    
    .animate-on-scroll.animate-in {
        opacity: 1;
        transform: translateY(0);
    }
    
    .feature-icon {
        transition: all 0.3s ease;
    }
`;
document.head.appendChild(style);

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SourcefulEnergy;
}

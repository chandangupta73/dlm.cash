// JWT Token Management
class AuthManager {
    static getAccessToken() {
        return localStorage.getItem('access_token');
    }
    
    static getRefreshToken() {
        return localStorage.getItem('refresh_token');
    }
    
    static setTokens(access, refresh) {
        localStorage.setItem('access_token', access);
        localStorage.setItem('refresh_token', refresh);
    }
    
    static clearTokens() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
    }
    
    static isAuthenticated() {
        return !!this.getAccessToken();
    }
    
    static logout() {
        this.clearTokens();
        window.location.href = '/auth/login/';
    }
    
    static async refreshToken() {
        const refresh = this.getRefreshToken();
        if (!refresh) return false;
        
        try {
            const response = await fetch('http://127.0.0.1:8000/api/v1/auth/refresh/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ refresh })
            });
            
            const data = await response.json();
            if (data.access) {
                this.setTokens(data.access, refresh);
                return true;
            }
        } catch (error) {
            console.error('Token refresh failed:', error);
        }
        
        return false;
    }
}

// API Request Helper with JWT
async function apiRequest(url, options = {}) {
    const token = AuthManager.getAccessToken();
    
    if (!token) {
        AuthManager.logout();
        return;
    }
    
    // Don't set Content-Type for FormData (browser will set it automatically with boundary)
    const isFormData = options.body instanceof FormData;
    
    const defaultOptions = {
        headers: {
            'Authorization': `Bearer ${token}`,
            ...options.headers
        }
    };
    
    // Only set Content-Type for JSON requests
    if (!isFormData) {
        defaultOptions.headers['Content-Type'] = 'application/json';
    }
    
    try {
        const response = await fetch(url, { ...defaultOptions, ...options });
        
        if (response.status === 401) {
            // Token expired, try to refresh
            if (await AuthManager.refreshToken()) {
                // Retry request with new token
                return apiRequest(url, options);
            } else {
                AuthManager.logout();
                return;
            }
        }
        
        return response;
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    }
}

// Utility function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Notification system
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Success and error notification helpers
function showSuccess(message) {
    showNotification(message, 'success');
}

function showError(message) {
    showNotification(message, 'danger');
}

// Check authentication status on page load
document.addEventListener('DOMContentLoaded', function() {
    // If user is on a protected page and not authenticated, redirect to login
    const protectedPages = ['/auth/dashboard', '/investment/', '/auth/profile'];
    const currentPath = window.location.pathname;
    
    if (protectedPages.some(page => currentPath.startsWith(page)) && !AuthManager.isAuthenticated()) {
        window.location.href = '/auth/login/';
    }
});


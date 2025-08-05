# Security Architecture - Sourceful Energy Web Application

## Overview

This document outlines the security measures implemented to protect the internal API endpoints from unauthorized access while maintaining a seamless user experience for the web application.

## Security Layers

### 1. Session-Based Token Authentication

**Problem Solved**: Replace "security by obscurity" with proper authentication.

**Implementation**:
- Each user session gets a unique, cryptographically secure token (32-byte URL-safe)
- Token stored in Flask session (server-side, encrypted)
- Frontend receives token via `/api-token` endpoint
- All internal API calls must include `X-Internal-API-Token` header

**Security Benefits**:
- Tokens are unpredictable and session-specific
- No hardcoded credentials in frontend code
- Automatic token rotation per session

### 2. Origin Validation

**Problem Solved**: Prevent cross-origin attacks and unauthorized API access.

**Implementation**:
- Validates `Origin` and `Referer` headers
- Ensures requests come from the same host
- Allows localhost for development

**Security Benefits**:
- Prevents external websites from calling internal API
- Blocks CSRF attacks from malicious sites
- Maintains same-origin policy

### 3. Rate Limiting

**Problem Solved**: Prevent abuse and DoS attacks.

**Implementation**:
- 100 requests per minute per IP address
- In-memory tracking with automatic cleanup
- Returns 429 status code when limit exceeded

**Security Benefits**:
- Prevents brute force attacks
- Limits impact of compromised sessions
- Protects server resources

### 4. Request Logging and Monitoring

**Problem Solved**: Detect and respond to security incidents.

**Implementation**:
- Logs all unauthorized access attempts
- Records IP addresses and request details
- Centralized logging with timestamps

**Security Benefits**:
- Early detection of attacks
- Forensic analysis capabilities
- Compliance with security standards

## API Endpoint Protection

### Internal API (`/_api/*`)
- **Protected**: ✅ All endpoints require valid session token
- **Rate Limited**: ✅ 100 requests/minute per IP
- **Origin Checked**: ✅ Must come from same domain
- **Logged**: ✅ All access attempts monitored

### Public Web Routes (`/`, `/status`, `/upload`)
- **Open Access**: ✅ Available to all users
- **Session Management**: ✅ Automatic token generation
- **HTTPS Ready**: ✅ Works with SSL/TLS

## Security Testing

### What's Protected
```bash
# These will be rejected with 403 Unauthorized
curl http://localhost:5004/_api/health
curl -H "Origin: https://evil.com" http://localhost:5004/_api/health
```

### What's Allowed
```bash
# These work normally
curl http://localhost:5004/
curl http://localhost:5004/status
curl http://localhost:5004/api-token
```

### Frontend Integration
```javascript
// Secure API calls from frontend
const response = await window.sourcefulEnergy.apiCall('/health');
```

## Production Recommendations

### 1. Environment Variables
```bash
# Set in production environment
export SECRET_KEY="your-super-secret-random-key-here"
export FLASK_ENV="production"
```

### 2. HTTPS Enforcement
```python
# Add to app configuration
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True  # No JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'  # CSRF protection
```

### 3. Reverse Proxy Security
```nginx
# Nginx configuration example
location /_api/ {
    # Block external access to internal API
    deny all;
    # Only allow from application server
    allow 127.0.0.1;
}
```

### 4. Content Security Policy
```html
<!-- Add to HTML templates -->
<meta http-equiv="Content-Security-Policy" 
      content="default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net;">
```

## Alternative Architectures

### Option 1: Server-Side Rendering (Highest Security)
- Move all API logic to server-side templates
- No client-side API calls
- Zero exposure of internal endpoints

### Option 2: JWT with Short Expiry
- Use JWT tokens with 5-minute expiry
- Automatic refresh mechanism
- Stateless authentication

### Option 3: WebSocket Communication
- Real-time communication channel
- No REST API exposure
- Encrypted message passing

## Monitoring and Alerts

### Security Events to Monitor
- Multiple failed authentication attempts
- Rate limit violations
- Origin validation failures
- Unusual request patterns

### Recommended Tools
- **Logging**: Python logging with structured format
- **Monitoring**: Application Performance Monitoring (APM)
- **Alerting**: Email/Slack notifications for security events

## Compliance Considerations

### Data Protection
- Session tokens are not logged
- User data encrypted in transit
- No persistent storage of sensitive data

### Security Standards
- Follows OWASP Web Security Guidelines
- Implements defense in depth
- Regular security testing recommended

## Summary

The implemented security model transforms the application from "security by obscurity" to a proper multi-layered security architecture while maintaining the web application's user experience. The internal API is genuinely protected, not just hidden.

**Key Benefits**:
- ✅ Proper authentication instead of obscure URLs
- ✅ Multiple security layers (tokens + origin + rate limiting)
- ✅ Production-ready security measures
- ✅ Seamless user experience maintained
- ✅ Monitoring and logging for security incidents

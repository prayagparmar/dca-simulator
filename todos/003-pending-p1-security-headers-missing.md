---
status: pending
priority: p1
issue_id: 003
tags: [code-review, security, web-security, headers]
dependencies: []
---

# Security Headers Missing

## Problem Statement

The Flask application doesn't set critical HTTP security headers, exposing users to clickjacking, MIME-type sniffing attacks, and cross-site scripting (XSS) via inline scripts.

**Why it matters**: Security headers are the first line of defense against common web attacks. Without them, attackers can embed the app in iframes for UI redressing, inject malicious content via MIME confusion, or exploit XSS vulnerabilities.

## Findings

**Source**: Security Sentinel Agent

- **Location**: `/Users/prayagparmar/Downloads/finance/app.py` (global configuration)
- **Missing Headers**:
  - `X-Frame-Options` - allows clickjacking attacks
  - `X-Content-Type-Options` - enables MIME-sniffing attacks
  - `X-XSS-Protection` - disables browser XSS filters (legacy, but defense-in-depth)
  - `Content-Security-Policy` - no protection against inline scripts
  - `Strict-Transport-Security` - allows downgrade to HTTP
- **Evidence**: No `@app.after_request` decorator or security headers middleware

**Attack Scenarios**:
1. **Clickjacking**: Attacker embeds app in invisible iframe, tricks user into clicking malicious actions
2. **MIME Sniffing**: Browser interprets JSON as HTML, executes injected scripts
3. **Missing CSP**: Inline scripts from XSS vulnerabilities execute without restriction

## Proposed Solutions

### Option 1: Flask-Talisman (Recommended)
- **Pros**:
  - Sets all security headers automatically
  - Enforces HTTPS
  - Configurable CSP policies
  - Maintained by Google
- **Cons**:
  - Adds dependency
  - May need CSP tuning for Chart.js CDN
- **Effort**: Low (1 hour)
- **Risk**: Low

**Implementation**:
```python
# requirements.txt: Flask-Talisman==1.1.0
from flask_talisman import Talisman

Talisman(app,
    content_security_policy={
        'default-src': "'self'",
        'script-src': ["'self'", 'cdn.jsdelivr.net'],  # Chart.js CDN
        'style-src': ["'self'", "'unsafe-inline'"],    # Inline styles
    },
    force_https=True  # Redirect HTTP to HTTPS in production
)
```

### Option 2: Manual Header Configuration
- **Pros**:
  - No dependencies
  - Full control over headers
- **Cons**:
  - More code to maintain
  - Easy to forget headers
  - Must update manually as standards evolve
- **Effort**: Medium (2 hours)
- **Risk**: Medium - easy to misconfigure

**Implementation**:
```python
@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'"
    )
    if request.is_secure:  # Only on HTTPS
        response.headers['Strict-Transport-Security'] = (
            'max-age=31536000; includeSubDomains'
        )
    return response
```

### Option 3: nginx Reverse Proxy Headers
- **Pros**:
  - Centralized security configuration
  - No application code changes
- **Cons**:
  - Requires nginx setup
  - Less portable (tied to infrastructure)
- **Effort**: Medium (nginx configuration)
- **Risk**: Low

## Recommended Action

**Implement Option 1 (Flask-Talisman)** for comprehensive protection with minimal code.

**CSP Considerations**:
- Chart.js loaded from `cdn.jsdelivr.net` - must whitelist in `script-src`
- Inline styles in `style.css` - require `'unsafe-inline'` (consider refactoring)
- No inline scripts in current codebase (good!)

## Technical Details

**Affected Files**:
- `requirements.txt` - add Flask-Talisman
- `app.py` - initialize Talisman with CSP policy
- `tests/test_security_headers.py` - new test file

**API Changes**: None (headers are transparent to client)

**Header Values**:
```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'; script-src 'self' cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

## Acceptance Criteria

- [ ] Flask-Talisman installed and configured
- [ ] All security headers present in responses
- [ ] CSP allows Chart.js from cdn.jsdelivr.net
- [ ] CSP blocks inline scripts (test with injected `<script>` tag)
- [ ] Test coverage for security headers (check each header)
- [ ] HTTPS enforced in production (redirects HTTP → HTTPS)
- [ ] No CSP violations in browser console on normal usage

## Work Log

### 2025-11-29
- **Discovered**: Security Sentinel identified missing security headers
- **Impact**: P1 - Essential for production deployment

## Resources

- [Flask-Talisman Documentation](https://github.com/GoogleCloudPlatform/flask-talisman)
- [OWASP Secure Headers Project](https://owasp.org/www-project-secure-headers/)
- [MDN Content Security Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [Security Headers Checker](https://securityheaders.com/)

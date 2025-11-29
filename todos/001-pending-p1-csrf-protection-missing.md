---
status: pending
priority: p1
issue_id: 001
tags: [code-review, security, web-security]
dependencies: []
---

# CSRF Protection Missing

## Problem Statement

The Flask application lacks CSRF (Cross-Site Request Forgery) protection on state-changing POST endpoints, exposing users to attacks where malicious sites can trigger unauthorized actions.

**Why it matters**: An attacker could create a malicious webpage that submits forms to `/calculate` on behalf of authenticated users, potentially exhausting server resources or triggering expensive API calls to Yahoo Finance.

## Findings

**Source**: Security Sentinel Agent

- **Location**: `/Users/prayagparmar/Downloads/finance/app.py:1816-1937`
- **Affected Endpoints**:
  - `POST /calculate` (line 1816)
  - POST requests have no CSRF token validation
- **Evidence**:
  ```python
  @app.route('/calculate', methods=['POST'])
  def calculate():
      data = request.json  # No CSRF validation
  ```

**Attack Scenario**:
1. User visits malicious site while logged into the DCA simulator
2. Malicious site submits hidden form to `/calculate` with attacker-controlled parameters
3. Request executes with user's session, consuming resources

**Severity**: CRITICAL (P1) - Blocks merge for production deployment

## Proposed Solutions

### Option 1: Flask-WTF with CSRF Tokens (Recommended)
- **Pros**:
  - Industry-standard solution
  - Easy integration with Flask
  - Handles token generation, storage, and validation automatically
- **Cons**:
  - Adds dependency (Flask-WTF)
  - Requires frontend changes to include token in AJAX requests
- **Effort**: Medium (2-3 hours)
- **Risk**: Low - well-documented pattern

**Implementation**:
```python
# Install: pip install Flask-WTF
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)

# In template: <meta name="csrf-token" content="{{ csrf_token() }}">
# In script.js: Add header to fetch requests
```

### Option 2: Custom CSRF Token Implementation
- **Pros**: No new dependencies
- **Cons**:
  - More code to maintain
  - Higher risk of implementation bugs
  - Reinventing the wheel
- **Effort**: High (4-6 hours)
- **Risk**: Medium - easy to get wrong

### Option 3: SameSite Cookie Attribute (Partial Mitigation)
- **Pros**: Simple configuration change
- **Cons**:
  - Only partial protection
  - Browser compatibility varies
  - Not a complete CSRF defense
- **Effort**: Low (15 minutes)
- **Risk**: Low, but insufficient alone

## Recommended Action

**Implement Option 1 (Flask-WTF)** immediately before production deployment.

**Steps**:
1. Add `Flask-WTF==1.2.1` to requirements.txt
2. Initialize CSRFProtect in app.py
3. Add CSRF token meta tag to templates/index.html
4. Update static/script.js to include token in fetch headers
5. Test form submissions with valid/invalid tokens
6. Add test case for CSRF protection

## Technical Details

**Affected Files**:
- `requirements.txt` - add Flask-WTF
- `app.py` - initialize CSRF protection
- `templates/index.html` - add meta tag
- `static/script.js` - include token in requests
- `tests/test_security.py` - new test file

**API Changes**: None (CSRF validation is transparent to valid requests)

**Database Impact**: None

## Acceptance Criteria

- [ ] Flask-WTF installed and configured
- [ ] All POST endpoints validate CSRF tokens
- [ ] Frontend includes CSRF token in all AJAX requests
- [ ] Test coverage for CSRF validation (valid/invalid tokens)
- [ ] POST requests without valid token return 400 Bad Request
- [ ] Documentation updated with CSRF setup instructions

## Work Log

### 2025-11-29
- **Discovered**: Security Sentinel agent identified missing CSRF protection during code review
- **Impact**: Classified as P1 (blocks production merge)

## Resources

- [Flask-WTF Documentation](https://flask-wtf.readthedocs.io/en/stable/)
- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [Similar pattern in Flask apps](https://flask-wtf.readthedocs.io/en/stable/csrf.html)

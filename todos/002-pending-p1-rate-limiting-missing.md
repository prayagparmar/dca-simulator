---
status: pending
priority: p1
issue_id: 002
tags: [code-review, security, dos-prevention, performance]
dependencies: []
---

# Rate Limiting Missing on API Endpoints

## Problem Statement

The `/calculate` and `/search` endpoints lack rate limiting, exposing the application to Denial of Service (DoS) attacks and Yahoo Finance API quota exhaustion.

**Why it matters**: An attacker could spam simulation requests to exhaust server CPU, memory, and external API quotas. This could make the service unavailable for legitimate users and potentially trigger Yahoo Finance rate limits that block all requests.

## Findings

**Source**: Security Sentinel Agent

- **Location**: `/Users/prayagparmar/Downloads/finance/app.py:1816, 1939`
- **Affected Endpoints**:
  - `POST /calculate` (expensive: fetches historical data, runs simulations)
  - `GET /search` (calls external Yahoo Finance API)
- **Evidence**: No rate limiting decorators or middleware in app.py

**Attack Scenario**:
1. Attacker scripts 1000 requests/second to `/calculate`
2. Each request fetches 10+ years of stock data from Yahoo Finance
3. Server exhausts memory, Yahoo blocks IP, legitimate users get errors

**Resource Consumption per Request**:
- `/calculate`: 2-4 seconds CPU, ~2MB memory, 2-3 external API calls
- `/search`: 100-200ms, 1 external API call

## Proposed Solutions

### Option 1: Flask-Limiter with Redis Backend (Recommended for Production)
- **Pros**:
  - Distributed rate limiting (works across multiple app instances)
  - Persistent storage (limits survive restarts)
  - Flexible limits (per-IP, per-endpoint, global)
- **Cons**:
  - Adds Redis dependency
  - More infrastructure to manage
- **Effort**: Medium (3-4 hours including Redis setup)
- **Risk**: Low - battle-tested solution

**Implementation**:
```python
# requirements.txt: Flask-Limiter==3.5.0, redis==5.0.1
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379"
)

@app.route('/calculate', methods=['POST'])
@limiter.limit("10 per minute")  # Adjust based on load testing
def calculate():
    ...

@app.route('/search')
@limiter.limit("30 per minute")
def search():
    ...
```

### Option 2: Flask-Limiter with In-Memory Storage (Simple, Development)
- **Pros**:
  - No Redis required
  - Easy setup
  - Good for single-instance deployments
- **Cons**:
  - Limits reset on restart
  - Doesn't work with multiple app instances (load balancer scenario)
- **Effort**: Low (1-2 hours)
- **Risk**: Low

**Implementation**:
```python
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    storage_uri="memory://"  # In-memory storage
)
```

### Option 3: Nginx Rate Limiting (Infrastructure Layer)
- **Pros**:
  - Offloads rate limiting from application
  - Very fast (C implementation)
  - Protects entire site
- **Cons**:
  - Requires nginx configuration
  - Less flexible per-route limits
  - Harder to customize error messages
- **Effort**: Medium (2-3 hours)
- **Risk**: Low

## Recommended Action

**Implement Option 2 (Flask-Limiter with in-memory storage)** for immediate protection, then migrate to Option 1 (Redis) when scaling beyond single instance.

**Suggested Limits**:
- `/calculate`: 10 requests/minute per IP (simulation is expensive)
- `/search`: 30 requests/minute per IP (autocomplete can fire rapidly)
- Global: 100 requests/minute per IP (across all endpoints)

## Technical Details

**Affected Files**:
- `requirements.txt` - add Flask-Limiter
- `app.py` - initialize limiter and add decorators
- `static/script.js` - handle 429 Too Many Requests responses
- `tests/test_rate_limiting.py` - new test file

**API Changes**:
- Returns `429 Too Many Requests` when limit exceeded
- Response includes `Retry-After` header

**Error Response Format**:
```json
{
  "error": "Rate limit exceeded. Please try again in 42 seconds.",
  "retry_after": 42
}
```

## Acceptance Criteria

- [ ] Flask-Limiter installed and configured
- [ ] `/calculate` limited to 10 requests/minute per IP
- [ ] `/search` limited to 30 requests/minute per IP
- [ ] Rate limit errors return 429 status with retry information
- [ ] Frontend displays user-friendly rate limit message
- [ ] Test coverage for rate limiting (normal usage, limit exceeded, retry)
- [ ] Logging added for rate limit violations (security monitoring)

## Work Log

### 2025-11-29
- **Discovered**: Security Sentinel identified missing rate limiting during code review
- **Impact**: P1 - Critical for production (DoS vulnerability)

## Resources

- [Flask-Limiter Documentation](https://flask-limiter.readthedocs.io/)
- [OWASP Rate Limiting Guide](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html)
- [HTTP 429 Status Code](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429)

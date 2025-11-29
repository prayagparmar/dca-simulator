---
status: pending
priority: p2
issue_id: 009
tags: [code-review, dependencies, reliability, production]
dependencies: []
---

# Production Dependency Instability - yfinance Library

## Problem Statement

The application has a critical external dependency on Yahoo Finance API via the `yfinance` library, which has shown instability in production (3 emergency fixes in 15 minutes). There's no fallback data source, no rate limit handling, and no request retry logic that could prevent service disruption.

**Why it matters**: The entire application is useless if Yahoo Finance is down or rate-limits our requests. Recent git history shows version ping-pong (0.2.66 → 0.2.40 → 0.2.66) due to build issues on Render.com. One bad Yahoo Finance API change or rate limit blocks all users.

## Findings

**Source**: Git History Analyzer + Security Sentinel

- **Location**: Git commits from 2025-11-28, app.py:702-761
- **Instability Evidence** (Git History):
  - **12:58 PM**: Commit `7488591` - Update to yfinance 0.2.66
  - **13:03 PM**: Commit `dcb3bdb` - Revert to yfinance 0.2.40 (0.2.66 breaks Render build)
  - **13:08 PM**: Commit `c0f01cf` - Revert back to 0.2.66 ("Use stable yfinance 0.2.40 for production reliability")
  - **Root Cause**: yfinance 0.2.66 requires `curl-cffi` which fails on Render.com

- **No Resilience Mechanisms**:
  - No retry logic for failed API calls ❌
  - No rate limit detection/handling ❌
  - No fallback data source ❌
  - No request timeout configured ❌
  - No circuit breaker pattern ❌

**Current Code** (app.py:733):
```python
hist = stock.history(start=start_date, end=end_date, auto_adjust=False)
# No error handling, no retry, no timeout
```

**Risk Scenarios**:
1. Yahoo Finance API goes down → All simulations fail
2. Yahoo changes API format → yfinance breaks, app breaks
3. Rate limit exceeded → All users blocked for hours
4. Slow Yahoo response → App hangs indefinitely (no timeout)

## Proposed Solutions

### Option 1: Add Retry Logic with Exponential Backoff (Immediate)
- **Pros**:
  - Handles transient failures (network glitches, temporary API issues)
  - Standard pattern for API resilience
  - Low effort
- **Cons**:
  - Doesn't solve rate limiting or permanent outages
  - Adds latency on failures (retry delay)
- **Effort**: Low (1-2 hours)
- **Risk**: Very Low

**Implementation**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError))
)
def fetch_stock_data(ticker, start_date, end_date, auto_adjust=False):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date, end=end_date, auto_adjust=auto_adjust)

        if hist.empty or hist['Close'].isnull().any():
            raise ValueError(f"Invalid/incomplete data for {ticker}")

        return hist
    except Exception as e:
        logger.error(f"Failed to fetch {ticker}: {e}")
        raise

# Retries: wait 2s, then 4s, then 8s before giving up
```

### Option 2: Add Fallback Data Source (Medium-Term)
- **Pros**:
  - True redundancy (if Yahoo fails, use alternative)
  - Protects against Yahoo API deprecation
  - Better SLA for users
- **Cons**:
  - Requires alternative data provider (Alpha Vantage, IEX Cloud, etc.)
  - May require paid API key
  - Data format differences to handle
- **Effort**: High (1-2 days)
- **Risk**: Medium

**Implementation**:
```python
def fetch_stock_data(ticker, start_date, end_date):
    try:
        return fetch_from_yfinance(ticker, start_date, end_date)
    except Exception as e:
        logger.warning(f"yfinance failed: {e}, trying fallback")
        return fetch_from_alpha_vantage(ticker, start_date, end_date)
```

**Fallback Options**:
- Alpha Vantage (500 requests/day free tier)
- IEX Cloud (50,000 requests/month free tier)
- Polygon.io (historical data, paid)

### Option 3: Local Data Caching with Stale-While-Revalidate (Best Long-Term)
- **Pros**:
  - Serves cached data if API down (better than nothing)
  - Reduces API calls (faster, cheaper)
  - Combined with Option 1, provides best resilience
- **Cons**:
  - Stale data risk (users see old prices)
  - Requires cache invalidation strategy
- **Effort**: Medium (3-4 hours)
- **Risk**: Low

**Implementation**:
```python
import redis
import pickle

def fetch_stock_data_with_cache(ticker, start_date, end_date):
    cache_key = f"stock:{ticker}:{start_date}:{end_date}"
    cached = redis_client.get(cache_key)

    try:
        # Try fresh data
        data = fetch_from_yfinance(ticker, start_date, end_date)
        redis_client.setex(cache_key, 86400, pickle.dumps(data))  # Cache 24h
        return data
    except Exception as e:
        logger.error(f"API failed: {e}")

        # Serve stale cache if available
        if cached:
            logger.warning(f"Serving stale data for {ticker}")
            return pickle.loads(cached)

        raise  # No cache, can't recover
```

## Recommended Action

**Immediate (This Week)**:
- Implement Option 1 (Retry logic with tenacity)
- Add request timeout to yfinance calls: `stock.history(..., timeout=10)`
- Add logging for API failures (monitor frequency)

**Next Month**:
- Implement Option 3 (Caching layer with Redis)
- Set up monitoring/alerting for Yahoo Finance failures

**Next Quarter**:
- Evaluate Option 2 (Fallback data source) if Yahoo reliability issues continue

## Technical Details

**Affected Files**:
- `requirements.txt` - add `tenacity==8.2.3`
- `app.py` - add retry decorator to `fetch_stock_data()`
- `app.py` - add timeout parameter to yfinance calls
- `tests/test_data_resilience.py` - new test file

**Retry Configuration**:
- Max attempts: 3
- Initial wait: 2 seconds
- Max wait: 10 seconds
- Exponential backoff multiplier: 2x
- Retry on: ConnectionError, TimeoutError, HTTPError (5xx)

**Monitoring Metrics**:
- API success rate (target: >99%)
- Average response time (target: <2s)
- Retry frequency (alert if >10% of requests retry)
- Cache hit rate (target: >80% for popular tickers)

## Acceptance Criteria

- [ ] `tenacity` library installed
- [ ] Retry decorator added to data fetching function
- [ ] Timeout configured for yfinance calls (10 seconds)
- [ ] Logging added for:
  - [ ] API failures
  - [ ] Retry attempts
  - [ ] Timeout events
- [ ] Test coverage for retry scenarios:
  - [ ] Success after 1 retry
  - [ ] Success after 3 retries
  - [ ] Failure after max retries
  - [ ] Timeout handling
- [ ] Documentation updated with dependency stability notes

## Work Log

### 2025-11-29
- **Discovered**: Git History Analyzer found yfinance version instability (3 commits in 15 min)
- **Impact**: P2 - Production reliability risk
- **Evidence**: Version ping-pong, build failures on Render.com

## Resources

- [Tenacity Retry Library](https://tenacity.readthedocs.io/)
- [yfinance GitHub Issues](https://github.com/ranaroussi/yfinance/issues)
- [Alpha Vantage API](https://www.alphavantage.co/)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)

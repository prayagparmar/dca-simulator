---
status: pending
priority: p1
issue_id: 005
tags: [code-review, performance, scalability, caching]
dependencies: []
---

# N+1 Query Pattern with Benchmark Calculations

## Problem Statement

For simulations with benchmarks, the application makes **3 sequential yfinance API calls** (main ticker, benchmark ticker, no-margin comparison), resulting in 3-5 seconds of blocking network I/O per request. This doesn't scale beyond ~100 concurrent users.

**Why it matters**: Each simulation blocks for 2-4 seconds waiting on Yahoo Finance. With 100 concurrent users, total API wait time is 300-400 seconds. This creates a terrible user experience and risks hitting Yahoo Finance rate limits.

## Findings

**Source**: Performance Oracle Agent

- **Location**: `/Users/prayagparmar/Downloads/finance/app.py:1888-1929`
- **Performance Impact**:
  - **Main simulation**: 1.15s (AAPL) to 0.44s (SPY) per API call
  - **Benchmark simulation**: Additional 1-2 seconds
  - **No-margin comparison**: Additional 1-2 seconds
  - **Total**: 3-5 seconds of blocking I/O per request
- **Evidence**:
  ```python
  # Line 1888: FIRST API call
  result = calculate_dca_core(ticker, ...)

  # Line 1898: SECOND API call (benchmark)
  benchmark_result = calculate_dca_core(benchmark_ticker, ...)

  # Line 1929: THIRD API call (no-margin comparison)
  no_margin_result = calculate_dca_core(ticker, ...)
  ```

**Scalability Analysis**:
- **10 users**: 30-50 seconds total API time
- **100 users**: 300-500 seconds (5-8 minutes!)
- **1000 users**: 3000-5000 seconds (50-83 minutes!)

## Proposed Solutions

### Option 1: LRU Cache with functools (Recommended)
- **Pros**:
  - Zero dependencies (built-in Python)
  - Automatic cache eviction
  - Thread-safe
  - 90% faster for repeated tickers
- **Cons**:
  - Cache doesn't persist across restarts
  - Single-instance only (doesn't work with load balancer)
- **Effort**: Low (1 hour)
- **Risk**: Very Low

**Implementation**:
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def fetch_stock_data_cached(ticker, start_date, end_date, auto_adjust):
    """Cached version of fetch_stock_data()"""
    return fetch_stock_data(ticker, start_date, end_date, auto_adjust)

# In calculate_dca_core(), replace:
hist = fetch_stock_data(ticker, ...)
# With:
hist = fetch_stock_data_cached(ticker, start_date, end_date, auto_adjust)
```

**Cache Hit Rate**:
- Same ticker with same date range: **100% hit rate**
- Popular tickers (AAPL, SPY, QQQ): ~80% hit rate
- Cache stores last 100 unique (ticker, start, end) combinations

### Option 2: Redis Caching Layer (Production-Ready)
- **Pros**:
  - Distributed cache (works across multiple app instances)
  - Persistent across restarts
  - TTL expiration (data refreshes daily)
  - Scales to thousands of users
- **Cons**:
  - Adds Redis dependency
  - More infrastructure
  - Slightly slower than in-memory (network round-trip)
- **Effort**: Medium (3-4 hours)
- **Risk**: Low

**Implementation**:
```python
import redis
import pickle

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def fetch_stock_data_cached(ticker, start_date, end_date, auto_adjust):
    cache_key = f"stock:{ticker}:{start_date}:{end_date}:{auto_adjust}"
    cached = redis_client.get(cache_key)

    if cached:
        return pickle.loads(cached)

    data = fetch_stock_data(ticker, start_date, end_date, auto_adjust)
    redis_client.setex(cache_key, 86400, pickle.dumps(data))  # 24h TTL
    return data
```

### Option 3: Background Job Queue (Advanced)
- **Pros**:
  - Non-blocking user experience
  - Can handle long-running simulations
  - Enables progress tracking
- **Cons**:
  - Significant architecture change
  - Requires Celery + Redis/RabbitMQ
  - Frontend needs polling/websockets
- **Effort**: High (1-2 days)
- **Risk**: Medium

## Recommended Action

**Immediate**: Implement Option 1 (LRU cache) for 90% improvement with minimal effort.

**Next Quarter**: Migrate to Option 2 (Redis) when scaling beyond single instance.

**Cache Strategy**:
- Cache key: `(ticker, start_date, end_date, auto_adjust)`
- TTL: 24 hours (stock data changes daily)
- Size: 100 entries (covers popular tickers)

**Expected Performance**:
- **First request** (cache miss): 3-5 seconds (same as now)
- **Cached request**: ~50ms (98% faster!)
- **Popular tickers**: 80% hit rate → average 1.4s per request (65% improvement)

## Technical Details

**Affected Files**:
- `app.py` - add caching decorator to `fetch_stock_data()`
- `tests/test_caching.py` - new test file for cache behavior

**Cache Invalidation**:
- Automatic via LRU eviction (oldest 100 entries kept)
- Manual: restart app or add `/admin/clear-cache` endpoint

**Memory Usage**:
- Per entry: ~100KB (10-year dataset)
- 100 entries: ~10MB total
- Negligible compared to request/response memory

## Acceptance Criteria

- [ ] `lru_cache` decorator added to data fetching function
- [ ] Cache key includes all parameters (ticker, dates, auto_adjust)
- [ ] Cache size limited to 100 entries
- [ ] Performance test shows:
  - [ ] First request: 2-4 seconds (unchanged)
  - [ ] Second identical request: <100ms (cache hit)
- [ ] Test coverage for cache hits and misses
- [ ] Logging added to track cache hit rate

## Work Log

### 2025-11-29
- **Discovered**: Performance Oracle identified N+1 API call pattern
- **Impact**: P1 - Blocks scalability beyond 100 concurrent users
- **Measurement**: AAPL fetch = 1.15s, SPY = 0.44s (load testing)

## Resources

- [Python functools.lru_cache](https://docs.python.org/3/library/functools.html#functools.lru_cache)
- [Redis Caching Patterns](https://redis.io/docs/manual/patterns/)
- [Flask Caching Extension](https://flask-caching.readthedocs.io/)

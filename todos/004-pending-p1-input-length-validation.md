---
status: pending
priority: p1
issue_id: 004
tags: [code-review, security, input-validation]
dependencies: []
---

# Missing Input Length Limits on Ticker Symbols

## Problem Statement

The `/calculate` endpoint accepts unbounded string inputs for `ticker` and `benchmark_ticker`, potentially enabling buffer overflow attacks, memory exhaustion, or injection attacks via excessively long inputs.

**Why it matters**: Without length validation, an attacker could submit a 1MB ticker string that consumes excessive memory, crashes the application, or exploits downstream string processing vulnerabilities in pandas/yfinance.

## Findings

**Source**: Security Sentinel Agent

- **Location**: `/Users/prayagparmar/Downloads/finance/app.py:1819-1843`
- **Vulnerable Parameters**:
  - `ticker` (line 1819) - no length or format validation
  - `benchmark_ticker` (line 1825) - no length or format validation
- **Evidence**:
  ```python
  ticker = data.get('ticker')  # Could be 1MB+ string
  benchmark_ticker = data.get('benchmark_ticker')
  # Passed directly to yfinance API and string formatting
  ```

**Attack Scenarios**:
1. Submit ticker with 1,000,000 characters → memory exhaustion
2. Submit ticker with special characters like `"../../etc/passwd"` → path traversal attempt (unlikely to work, but shows no validation)
3. Submit ticker with SQL-like syntax → potential injection if passed to database (not applicable here, but defense-in-depth)

## Proposed Solutions

### Option 1: Length and Format Validation (Recommended)
- **Pros**:
  - Blocks both length attacks and malformed inputs
  - Regex validation ensures only valid ticker formats
  - Provides clear error messages to users
- **Cons**:
  - Regex may be too strict for some international tickers
- **Effort**: Low (30 minutes)
- **Risk**: Low

**Implementation**:
```python
import re

TICKER_PATTERN = re.compile(r'^[A-Z0-9.\-]{1,10}$')

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    ticker = data.get('ticker', '').strip().upper()

    # Validation
    if not ticker:
        return jsonify({'error': 'Ticker is required'}), 400
    if len(ticker) > 10:
        return jsonify({'error': 'Ticker must be 10 characters or less'}), 400
    if not TICKER_PATTERN.match(ticker):
        return jsonify({'error': 'Invalid ticker format. Use A-Z, 0-9, dots, and hyphens only'}), 400

    # Same for benchmark_ticker
    benchmark_ticker = data.get('benchmark_ticker', '').strip().upper()
    if benchmark_ticker and not TICKER_PATTERN.match(benchmark_ticker):
        return jsonify({'error': 'Invalid benchmark ticker format'}), 400
```

### Option 2: Length-Only Validation
- **Pros**:
  - Simple implementation
  - Less restrictive (allows unusual formats)
- **Cons**:
  - Doesn't prevent malformed inputs
  - No format validation
- **Effort**: Low (15 minutes)
- **Risk**: Medium - partial protection

**Implementation**:
```python
if len(ticker) > 10:
    return jsonify({'error': 'Ticker too long'}), 400
```

### Option 3: Flask Request Size Limit
- **Pros**:
  - Protects entire request body
  - One-line configuration
- **Cons**:
  - Doesn't validate individual fields
  - May allow 10-character ticker with 1MB of other data
- **Effort**: Very Low (5 minutes)
- **Risk**: Medium - too coarse-grained

**Implementation**:
```python
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024  # 1MB max request
```

## Recommended Action

**Implement Option 1 (Length + Format Validation)** for comprehensive protection.

**Ticker Format Standards**:
- US stocks: 1-5 uppercase letters (e.g., AAPL, MSFT, BRK.B)
- Max length: 10 characters (covers most international tickers)
- Allowed characters: A-Z, 0-9, dot (.), hyphen (-)

**Examples**:
- ✅ Valid: `AAPL`, `BRK.B`, `TSM`, `SPY`, `VOO`
- ❌ Invalid: `apple`, `AAPL<script>`, `../../../etc`, `VERYLONGTICKERSYMBOL`

## Technical Details

**Affected Files**:
- `app.py` - add validation to `/calculate` route
- `tests/test_input_validation.py` - test cases for valid/invalid inputs

**API Changes**:
- Returns `400 Bad Request` for invalid ticker formats
- Error message indicates specific validation failure

**Edge Cases**:
- Empty ticker: Return 400 with "Ticker is required"
- Lowercase ticker: Auto-convert to uppercase (`.upper()`)
- Whitespace: Strip leading/trailing spaces (`.strip()`)

## Acceptance Criteria

- [ ] Ticker length limited to 10 characters
- [ ] Ticker format validated with regex pattern
- [ ] Benchmark ticker validated with same rules
- [ ] Invalid formats return 400 with descriptive error
- [ ] Test coverage for:
  - [ ] Valid tickers (AAPL, BRK.B, etc.)
  - [ ] Too-long ticker (11+ characters)
  - [ ] Invalid characters (lowercase, special chars)
  - [ ] Empty/null ticker
  - [ ] Whitespace handling
- [ ] Frontend shows validation errors in UI

## Work Log

### 2025-11-29
- **Discovered**: Security Sentinel identified unbounded input vulnerability
- **Impact**: P1 - Blocks merge (security vulnerability)

## Resources

- [Yahoo Finance Ticker Format](https://finance.yahoo.com/lookup)
- [OWASP Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
- [Python re module documentation](https://docs.python.org/3/library/re.html)

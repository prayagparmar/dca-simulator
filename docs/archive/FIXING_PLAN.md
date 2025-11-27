# Comprehensive Fixing Plan for DCA Simulator

**Date:** November 25, 2025
**Total Issues:** 19 identified
**Estimated Effort:** 8-12 hours development + 4 hours testing

---

## Phase 1: Critical Bug Fixes (Priority 1 - Immediate)

### 1.1 Fix NaN Price Handling
**File:** `app.py`
**Line:** 48-51
**Effort:** 15 minutes

**Current Code:**
```python
if hist.empty:
    return None
```

**Fixed Code:**
```python
if hist.empty:
    return None

# Validate price data - handle NaN/None values
if hist['Close'].isnull().any():
    print(f"WARNING: {ticker} has missing price data in range")
    return None
```

**Test:** `test_flaw_empty_price_data` should pass

---

### 1.2 Fix Interest Calculation for Partial Months
**File:** `app.py`
**Line:** 162-187
**Effort:** 1 hour

**Problem:** Interest not charged for first partial month

**Solution Option A (Simple):**
Charge interest on day 1 if borrowing exists:
```python
if last_interest_month is None:
    last_interest_month = current_month
    # Charge pro-rated interest for partial first month if already borrowed
    if borrowed_amount > 0:
        fed_rate = get_fed_funds_rate(date_str)
        monthly_rate = (fed_rate + 0.005) / 12
        interest_charge = borrowed_amount * monthly_rate
        total_interest_paid += interest_charge
        # Pay from cash or capitalize
        if current_balance is not None:
            if current_balance >= interest_charge:
                current_balance -= interest_charge
            else:
                if current_balance > 0:
                    interest_charge -= current_balance
                    current_balance = 0
                borrowed_amount += interest_charge
```

**Solution Option B (Accurate):**
Calculate pro-rated interest based on days in month:
```python
# Track first borrow date, calculate days since first borrow
# Charge interest proportional to days held in month
```

**Recommendation:** Use Option A for MVP, Option B for v3.0

**Test:** `test_flaw_interest_charged_on_first_day_of_month` should pass

---

### 1.3 Add Input Validation
**File:** `app.py`
**Line:** 427-445 (in `/calculate` endpoint)
**Effort:** 30 minutes

**Add after line 444:**
```python
# Validate input ranges
if amount < 0:
    return jsonify({'error': 'Daily amount must be non-negative'}), 400

if initial_amount < 0:
    return jsonify({'error': 'Initial investment must be non-negative'}), 400

if margin_ratio < 1.0 or margin_ratio > 2.0:
    return jsonify({'error': 'Margin ratio must be between 1.0 and 2.0'}), 400

if maintenance_margin <= 0 or maintenance_margin >= 1.0:
    return jsonify({'error': 'Maintenance margin must be between 0 and 1'}), 400

if account_balance is not None and account_balance < 0:
    return jsonify({'error': 'Account balance must be non-negative'}), 400
```

**Test:** `test_invalid_margin_ratio`, `test_negative_amounts` should return 400 errors

---

### 1.4 Fix Dividend Date Alignment
**File:** `app.py`
**Line:** 57-71
**Effort:** 30 minutes

**Current Code:**
```python
dividends = stock.dividends
# Filter dividends within range
if start_date and end_date:
    try:
        dividends = dividends[start_date:end_date]
    except Exception as e:
        print(f"DEBUG: Error slicing dividends: {e}")
        pass

if isinstance(dividends.index, pd.DatetimeIndex):
    dividends.index = dividends.index.strftime('%Y-%m-%d')
```

**Fixed Code:**
```python
dividends = stock.dividends

# Ensure dividend index is DatetimeIndex before filtering
if not isinstance(dividends.index, pd.DatetimeIndex):
    try:
        dividends.index = pd.to_datetime(dividends.index)
    except:
        # If conversion fails, create empty dividend series
        dividends = pd.Series(dtype=float)

# Filter dividends within range
if start_date and end_date:
    try:
        dividends = dividends[start_date:end_date]
    except Exception as e:
        print(f"WARNING: Could not filter dividends for {ticker}: {e}")
        dividends = pd.Series(dtype=float)  # Use empty if filtering fails

# Convert to string format for consistent lookup
if isinstance(dividends.index, pd.DatetimeIndex):
    dividends.index = dividends.index.strftime('%Y-%m-%d')
```

**Test:** All dividend-related errors in test output should disappear

---

## Phase 2: High Priority Fixes (Priority 2 - Next Sprint)

### 2.1 Remove Duplicate Code
**File:** `app.py`
**Effort:** 5 minutes

**Line 93-94:** Remove duplicate `total_invested = 0`
**Line 398:** Remove duplicate `'net_portfolio': net_portfolio_values,`
**Line 416-417:** Remove duplicate `'current_leverage'` and `'margin_calls'` keys

---

### 2.2 Fix Equity Calculation Consistency
**File:** `app.py`
**Line:** 308
**Effort:** 5 minutes

**Change:**
```python
# Line 308 - Before
current_equity = current_portfolio_value + current_balance - borrowed_amount

# After (match line 214)
current_equity = current_portfolio_value + max(0, current_balance) - borrowed_amount
```

---

### 2.3 Prevent Negative Cash Balance
**File:** `app.py`
**Line:** After all cash operations
**Effort:** 15 minutes

**Add assertions/clamps:**
```python
# After line 177 (interest payment)
current_balance = max(0, current_balance)

# After line 303 (after buy)
current_balance = max(0, current_balance)

# After line 341 (after debt repayment)
current_balance = max(0, current_balance)
```

---

### 2.4 Fix Margin Call Formula Safety
**File:** `app.py`
**Line:** 326
**Effort:** 5 minutes

**Change:**
```python
# Before
target_portfolio_value = (borrowed_amount - current_balance) / (1 - maintenance_margin)

# After
target_portfolio_value = (borrowed_amount - max(0, current_balance)) / (1 - maintenance_margin)
```

---

### 2.5 Add Documentation Comments
**File:** `app.py`
**Line:** 127 (start of loop)
**Effort:** 10 minutes

**Add:**
```python
for date, row in hist.iterrows():
    """
    Daily order of operations (executed each trading day):
    1. Process dividends - paid on shares held overnight (before today's buy)
    2. Charge interest - monthly on first trading day of new month
    3. Execute daily purchase - buy shares with cash and/or margin
    4. Check margin requirements - force liquidation if equity < maintenance margin
    """

    date_str = date if isinstance(date, str) else date.strftime('%Y-%m-%d')
    price = row['Close']
```

---

### 2.6 Benchmark Margin Behavior Decision
**File:** `app.py`
**Line:** 457
**Effort:** 30 minutes (requires decision)

**Options:**

**Option A:** Always use no margin for benchmark
```python
benchmark_result = calculate_dca_core(
    benchmark_ticker, start_date, end_date, amount, initial_amount, reinvest,
    target_dates=result['dates'],
    account_balance=account_balance,
    margin_ratio=1.0,  # CHANGED: Always no margin for fair comparison
    maintenance_margin=maintenance_margin
)
```

**Option B:** Add UI toggle for benchmark margin mode

**Option C:** Keep current behavior but document it

**Recommendation:** Option A for simplicity

---

## Phase 3: Medium Priority Improvements (Priority 3 - Future Sprint)

### 3.1 Clarify Available Principal Logic
**File:** `app.py`
**Line:** 96
**Effort:** 10 minutes

**Add comment:**
```python
# Track user principal separately from account balance
# In infinite cash mode (None), principal tracking is disabled
# Dividends and margin don't count as principal - only user contributions
available_principal = account_balance if account_balance is not None else 0
```

---

### 3.2 Improve ROI Edge Case
**File:** `app.py`
**Line:** 410
**Effort:** 15 minutes

**Change:**
```python
# Before
'roi': round((((current_portfolio_value - borrowed_amount) - total_invested) / total_invested * 100), 2) if total_invested > 0 else 0,

# After (add special handling)
'roi': round((((current_portfolio_value - borrowed_amount) - total_invested) / total_invested * 100), 2) if total_invested > 0 else None,
```

**Frontend:** Display "N/A" when ROI is None

---

### 3.3 Store Raw Values in Time Series
**File:** `app.py`
**Line:** 356-375
**Effort:** 30 minutes

**Change rounding strategy:**
```python
# Before - round when appending
invested_values.append(round(total_invested, 2))

# After - append raw, round in summary only
invested_values.append(total_invested)

# Then at line 389, round for return:
return {
    'dates': dates,
    'invested': [round(v, 2) for v in invested_values],
    'portfolio': [round(v, 2) for v in portfolio_values],
    # ... etc
}
```

---

### 3.4 Add Maintenance Margin Validation
**File:** `app.py`
**Line:** 41 (function signature)
**Effort:** 5 minutes

**Add assertion:**
```python
def calculate_dca_core(ticker, start_date, end_date, amount, initial_amount, reinvest, target_dates=None, account_balance=None, margin_ratio=1.0, maintenance_margin=0.25):
    # Validate parameters
    assert 0 < maintenance_margin < 1.0, "Maintenance margin must be between 0 and 1"
    assert 1.0 <= margin_ratio <= 2.0, "Margin ratio must be between 1.0 and 2.0"

    # Fetch historical data
    try:
        ...
```

---

## Phase 4: Test Suite Improvements

### 4.1 Fix Mock Dividend Setup
**File:** All test files
**Effort:** 1 hour

**Fix setup_mock_data helper:**
```python
def setup_mock_data(self, prices, dividends=None):
    """Helper to create mock stock data"""
    mock_stock = MagicMock()
    dates = pd.date_range(start='2024-01-01', periods=len(prices), freq='D')

    # Return DataFrame with DatetimeIndex (not string index)
    mock_stock.history.return_value = pd.DataFrame({'Close': prices}, index=dates)

    if dividends:
        # Create Series with DatetimeIndex
        div_dates = [pd.to_datetime(d) for d in dividends.keys()]
        div_values = list(dividends.values())
        mock_stock.dividends = pd.Series(div_values, index=div_dates)
    else:
        mock_stock.dividends = pd.Series(dtype=float)

    self.mock_ticker.return_value = mock_stock
    return dates.strftime('%Y-%m-%d').tolist()
```

---

### 4.2 Remove Fragile Fed Funds Test
**File:** `tests/test_comprehensive_flaws.py`
**Line:** 567
**Effort:** 5 minutes

**Replace with integration test:**
```python
def test_fed_funds_rate_error_handling(self):
    """Test error handling returns default rate"""
    # Instead of mocking internal state, test with invalid date
    rate = get_fed_funds_rate('invalid-date')
    self.assertEqual(rate, 0.05, "Should return default 5% on error")
```

---

## Phase 5: Cleanup and Documentation

### 5.1 Create .gitignore
**File:** `.gitignore` (new file)
**Effort:** 5 minutes

**Content:**
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Virtual Environment
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Testing
.pytest_cache/
.coverage
htmlcov/
*.egg-info/

# OS
.DS_Store
Thumbs.db
```

---

### 5.2 Remove Unnecessary Files
**Files to remove:**
1. `TDD_COMPLIANCE_REPORT.md`
2. `TEST_COVERAGE_SUMMARY.md`
3. All `__pycache__/` directories

**Command:**
```bash
rm TDD_COMPLIANCE_REPORT.md TEST_COVERAGE_SUMMARY.md
find . -type d -name __pycache__ -exec rm -rf {} +
```

---

### 5.3 Update CLAUDE.md
**File:** `CLAUDE.md`
**Effort:** 15 minutes

**Add section:**
```markdown
## Known Bugs (Fixed in v2.3)

The following bugs were identified and fixed:
1. NaN price data handling
2. Interest calculation for partial months
3. Input validation missing
4. Dividend date alignment errors
5. Duplicate code blocks
6. Equity calculation inconsistency

See BUGS_AND_FLAWS_REPORT.md for full details.
```

---

## Testing Strategy

### Regression Testing Checklist

After each fix, run:

```bash
# Run all existing tests
python -m unittest discover tests/ -v

# Run comprehensive flaw tests
python -m unittest tests.test_comprehensive_flaws -v

# Specific critical tests
python -m unittest tests.test_comprehensive_flaws.TestCriticalFlaws.test_flaw_empty_price_data
python -m unittest tests.test_comprehensive_flaws.TestCriticalFlaws.test_flaw_interest_charged_on_first_day_of_month
python -m unittest tests.test_comprehensive_flaws.TestInputValidation.test_invalid_margin_ratio
python -m unittest tests.test_comprehensive_flaws.TestInputValidation.test_negative_amounts
```

### Manual Testing Checklist

1. [ ] Test with real ticker (AAPL) over 1 year with margin
2. [ ] Test with dividend stock (VTI) with reinvestment
3. [ ] Test with crypto (BTC-USD) crossing month boundary
4. [ ] Test with delisted stock or invalid ticker
5. [ ] Test benchmark comparison with and without margin
6. [ ] Test margin call scenario (CVNA 2022 crash)
7. [ ] Submit negative amounts via UI - should show error
8. [ ] Submit invalid margin ratio - should show error

---

## Implementation Order

### Sprint 1 (Week 1): Critical Fixes
- Day 1: Fix #1 (NaN handling) + Fix #4 (Dividend alignment)
- Day 2: Fix #2 (Interest calculation)
- Day 3: Fix #3 (Input validation) + Testing
- Day 4: Test suite fixes
- Day 5: Regression testing + deployment

### Sprint 2 (Week 2): High Priority
- Day 1: Remove duplicates + Equity consistency
- Day 2: Negative balance prevention + Margin formula
- Day 3: Documentation comments
- Day 4: Benchmark behavior decision + implementation
- Day 5: Testing + deployment

### Sprint 3 (Week 3): Medium Priority
- Day 1-2: Rounding strategy + Principal logic
- Day 3: ROI edge case + Maintenance margin validation
- Day 4: Cleanup + .gitignore
- Day 5: Documentation update

---

## Risk Assessment

| Fix | Risk Level | Mitigation |
|-----|-----------|------------|
| NaN handling | Low | Well-isolated check |
| Interest calculation | Medium | Could affect all margin simulations - extensive testing needed |
| Input validation | Low | Only affects API layer |
| Dividend alignment | Medium | Core data processing - test thoroughly |
| Remove duplicates | Low | Mechanical changes |
| Equity calculation | Medium | Affects margin logic - verify all margin tests pass |

---

## Success Criteria

### Definition of Done

- [ ] All 19 identified bugs fixed
- [ ] All existing tests pass (75+ tests)
- [ ] All new comprehensive flaw tests pass (30 tests)
- [ ] Manual testing checklist completed
- [ ] Code coverage > 85%
- [ ] Documentation updated
- [ ] No regression in existing functionality
- [ ] Performance impact < 5% (measure with 10-year simulation)

### Acceptance Criteria

1. **NaN Price Data:** Simulations with missing data return graceful error, not crash
2. **Interest Calculation:** Verified with known scenarios - interest matches manual calculation
3. **Input Validation:** Invalid inputs return 400 error with clear message
4. **Dividend Alignment:** No more "Error slicing dividends" messages in logs
5. **Code Quality:** No duplicate code, consistent formatting
6. **Margin Logic:** All margin tests pass, equity always calculated consistently

---

**Estimated Total Effort:**
- Development: 10-12 hours
- Testing: 4-6 hours
- Documentation: 2 hours
- **Total: 16-20 hours (2-3 developer days)**

---

**End of Fixing Plan**

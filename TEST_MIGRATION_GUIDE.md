# Test Mock Migration Guide

## Overview

This guide documents how to migrate test files from manual mock setup to shared `conftest.py` helpers. This migration eliminates **1,000+ lines of duplicate code** across the test suite.

## Current Status

**Completed**:
- ✅ `tests/conftest.py` - Shared helpers created (9 functions)
- ✅ `tests/test_calculations.py` - 4 of 12 methods migrated (33%)

**Remaining**:
- 📋 `tests/test_calculations.py` - 8 more methods
- 📋 21 other test files with 135+ instances

**Total Scope**:
- 22 test files
- 139 mock setup instances
- ~1,160 lines of duplicate code to remove

## Migration Pattern

### BEFORE (Old Pattern - 8-10 lines per test)

```python
@patch('app.yf.Ticker')
def test_something(self, mock_ticker):
    # Manual mock setup (8-10 lines of boilerplate)
    mock_stock = MagicMock()
    dates = pd.date_range(start='2023-01-01', periods=3, freq='D')
    data = {'Close': [100.0, 200.0, 300.0]}
    hist = pd.DataFrame(data, index=dates)
    mock_stock.history.return_value = hist
    mock_stock.dividends = pd.Series(dtype=float)
    mock_ticker.return_value = mock_stock

    # Test logic...
```

### AFTER (New Pattern - 1 line)

```python
@patch('app.yf.Ticker')
def test_something(self, mock_ticker):
    # Use shared helper (1 line)
    mock_ticker.return_value = create_mock_stock_data([100.0, 200.0, 300.0], start_date='2023-01-01')

    # Test logic...
```

**Savings**: 8 lines → 1 line = **88% reduction per test**

## Step-by-Step Migration

### Step 1: Add conftest import

At the top of the test file:

```python
from tests.conftest import create_mock_stock_data
```

Keep existing imports (MagicMock, pandas) for now - remove later if unused.

### Step 2: Identify the pattern

Look for this pattern in each test method:

```python
mock_stock = MagicMock()
dates = pd.date_range(...)
data = {'Close': [...]}
hist = pd.DataFrame(data, index=dates)
mock_stock.history.return_value = hist
mock_stock.dividends = pd.Series(...) # or specific dividends
mock_ticker.return_value = mock_stock
```

### Step 3: Replace with helper

**For simple price series (no dividends)**:
```python
mock_ticker.return_value = create_mock_stock_data(
    [100.0, 200.0, 300.0],
    start_date='2023-01-01'
)
```

**For price series with dividends**:
```python
mock_ticker.return_value = create_mock_stock_data(
    [100.0, 100.0, 100.0],
    dividends={'2023-01-02': 10.0},
    start_date='2023-01-01'
)
```

**For complex scenarios**, use specialized helpers from conftest.py:
- `create_trending_stock()` - Linear price increase
- `create_volatile_stock()` - Random price movements
- `create_dividend_stock()` - Quarterly dividends
- `create_crash_scenario()` - Market crash simulation

### Step 4: Test

After each file migration:

```bash
python -m unittest tests.test_<filename>
```

Ensure all tests pass before moving to next file.

## Available Helpers (conftest.py)

### Core Helpers

1. **`create_mock_stock_data(prices, dividends=None, start_date='2024-01-01')`**
   - Most common helper
   - Replaces 8-10 lines of boilerplate
   - Example: `create_mock_stock_data([100, 200, 300])`

2. **`create_trending_stock(start_price, end_price, num_days, start_date)`**
   - Linear price increase/decrease
   - Example: `create_trending_stock(100, 200, 30)`  # +3.45% daily

3. **`create_volatile_stock(base_price, volatility, num_days, start_date, seed)`**
   - Random price movements with specified volatility
   - Example: `create_volatile_stock(100, 0.20, 100)`  # 20% daily volatility

4. **`create_dividend_stock(price, num_days, quarterly_dividend, start_date)`**
   - Constant price with quarterly dividends
   - Example: `create_dividend_stock(100, 365, 0.75)`  # $0.75 quarterly

5. **`create_crash_scenario(peak_price, crash_pct, days_to_crash, days_after, start_date)`**
   - Market crash simulation for margin testing
   - Example: `create_crash_scenario(200, 0.50, 10, 30)`  # 50% crash over 10 days

### Convenience Functions

- `flat_price_mock(price, days)` - Quick flat price
- `simple_trend_mock(start, end, days)` - Quick trending price
- `with_dividends_mock(price, days, dividend_per_share)` - Quick dividend scenario

## Migration Priority (Recommended Order)

### Batch 1: Simple files (High ROI, Low Complexity)
1. ✅ `test_calculations.py` - **IN PROGRESS** (4/12 done)
2. `test_financial_accuracy.py` - Simple numerical tests
3. `test_data_validation.py` - Input validation tests

### Batch 2: Medium complexity
4. `test_margin_trading.py` - Margin scenarios
5. `test_prd_compliance.py` - Feature compliance
6. `test_edge_cases.py` - Edge case handling

### Batch 3: Complex scenarios
7. `test_withdrawal_*.py` - Withdrawal logic (3 files)
8. `test_integration_properties.py` - Integration tests
9. `test_benchmark_date_alignment.py` - Date alignment logic

### Batch 4: Specialized tests
10. `test_frequency_*.py` - Frequency features (2 files)
11. `test_analytics_*.py` - Analytics tests (2 files)
12. Remaining 9 files

## Expected Impact

### Lines of Code Reduction

| File | Instances | Lines Before | Lines After | Savings |
|------|-----------|--------------|-------------|---------|
| test_calculations.py | 12 | ~120 | ~24 | **96 lines** |
| test_margin_trading.py | ~15 | ~150 | ~30 | **120 lines** |
| test_withdrawal_*.py | ~30 | ~300 | ~60 | **240 lines** |
| Other 19 files | ~82 | ~820 | ~164 | **656 lines** |
| **TOTAL** | **139** | **~1,390** | **~278** | **~1,112 lines** |

**Total Reduction**: **~1,112 lines (80% of mock setup code)**

### Maintainability Benefits

- ✅ Single source of truth for mock data patterns
- ✅ Easier to update if yfinance API changes
- ✅ More readable tests (less boilerplate)
- ✅ Faster to write new tests
- ✅ Consistent mock data across test suite

## Common Patterns & Solutions

### Pattern: Side Effects (e.g., date filtering)

**Before**:
```python
def side_effect(start=None, end=None, **kwargs):
    if end:
        return hist[hist.index < end]
    return hist
mock_stock.history.side_effect = side_effect
```

**After**:
Still use side_effect, but create base data with helper:
```python
base_mock = create_mock_stock_data([100, 200, 300, 400, 500], start_date='2023-01-01')
def side_effect(start=None, end=None, **kwargs):
    hist = base_mock.history.return_value
    if end:
        return hist[hist.index < end]
    return hist
base_mock.history.side_effect = side_effect
mock_ticker.return_value = base_mock
```

### Pattern: Multiple tickers (benchmark tests)

The same mock is reused for all tickers (TEST, SPY, etc.):

```python
# This works because mock returns the same data for any ticker
mock_ticker.return_value = create_mock_stock_data([100, 200, 300])
```

### Pattern: Empty/invalid data

Use the helper but return appropriate data:

```python
# For empty data test
mock_ticker.return_value = create_mock_stock_data([])

# For invalid ticker test
mock_ticker.side_effect = Exception("Ticker not found")
```

## Testing Strategy

### After Each File Migration

1. Run the specific test file:
   ```bash
   python -m unittest tests.test_<filename>
   ```

2. Verify all tests pass (look for `OK` status)

3. Check for import errors or missing helper functions

### After Batch Completion

Run full test suite to ensure no regressions:

```bash
python -m unittest discover tests/
```

### Final Validation

Count total lines removed:

```bash
# Before migration
git show HEAD~1:tests/ | wc -l

# After migration
cat tests/*.py | wc -l

# Calculate difference
```

## Commit Strategy

Commit after each batch to keep changes reviewable:

```bash
git add tests/test_*.py
git commit -m "refactor: Migrate test batch 1 to use conftest helpers

- Migrated test_calculations.py (12 methods)
- Migrated test_financial_accuracy.py (8 methods)
- Migrated test_data_validation.py (6 methods)
- Removed 250 lines of duplicate mock setup

All tests pass: python -m unittest discover tests/"
```

## Troubleshooting

### Import Error: "No module named 'conftest'"

Use `from tests.conftest import` instead of `from conftest import`.

### Tests fail after migration

1. Check start_date matches original test data
2. Verify price array matches original Close prices exactly
3. Ensure dividends dict uses correct date format ('YYYY-MM-DD')
4. Compare original vs new mock output in debugger

### Helper doesn't support my scenario

1. Check if one of the specialized helpers works (trending, volatile, crash, etc.)
2. Create a new helper in conftest.py for your scenario
3. Or combine base helper with custom setup

## Next Steps

1. **Complete test_calculations.py** (8 more methods)
2. **Migrate Batch 1 files** (financial_accuracy, data_validation)
3. **Create PR** after each batch for easier review
4. **Continue incrementally** until all 139 instances migrated

## Success Criteria

- [ ] All 22 test files migrated
- [ ] All 139 mock setup instances replaced
- [ ] ~1,100 lines of code removed
- [ ] Full test suite passes: `python -m unittest discover tests/`
- [ ] No new test failures introduced
- [ ] Conftest helpers cover all common scenarios

---

**Estimated Effort**: 4-6 hours total (migrating ~25 tests/hour)
**Completed**: 4 tests (30 minutes)
**Remaining**: 135 tests (~5 hours)

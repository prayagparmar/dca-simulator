---
status: pending
priority: p1
issue_id: 007
tags: [code-review, testing, dry-violation, maintainability]
dependencies: []
---

# Test Mock Setup Duplicated Across 17 Files

## Problem Statement

The same yfinance mock setup code is duplicated ~145 times across 17 test files, totaling ~1,160 lines of redundant test infrastructure. Changes to mock data structure require updates in 17 locations.

**Why it matters**: When yfinance API changes (as seen in recent commits), every test file needs manual updates. This massive duplication violates DRY principle and makes test maintenance a nightmare. The test suite is 11,572 lines - 10% is duplicated mock setup.

## Findings

**Source**: Code Simplicity Reviewer + Pattern Recognition Specialist

- **Location**: 11 test files with duplicated mock setup
- **Duplication Stats**:
  - **Instances**: 145 tests with identical mock setup (8-10 lines each)
  - **Total Lines**: ~1,160 lines of duplicate code
  - **Percentage**: 10% of test suite (1,160 / 11,572 lines)
- **Evidence**: Every test file repeats this pattern:
  ```python
  @patch('app.yf.Ticker')
  def test_something(self, mock_ticker):
      mock_stock = MagicMock()
      dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
      hist = pd.DataFrame({'Close': [100] * len(dates)}, index=dates)
      mock_stock.history.return_value = hist
      mock_stock.dividends = pd.Series(dtype=float)
      mock_ticker.return_value = mock_stock
      # ... actual test logic
  ```

**Affected Test Files**:
- test_prd_compliance.py (4 instances)
- test_integration_properties.py (4 instances)
- test_calculations.py (~20 instances)
- test_margin_trading.py (~15 instances)
- test_withdrawal_*.py (30+ instances)
- 6 more files with 10+ instances each

## Proposed Solutions

### Option 1: Shared Test Fixtures with pytest (Recommended)
- **Pros**:
  - Single source of truth for mock data
  - Reusable across all test files
  - Easy to extend (add new data scenarios)
  - pytest fixtures are explicit and readable
- **Cons**:
  - Requires migration from unittest to pytest (already partially there)
  - Need to update all 145 test function signatures
- **Effort**: Medium (4-6 hours)
- **Risk**: Low (pytest is standard)

**Implementation**:
```python
# tests/conftest.py (CREATE THIS FILE)
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_stock_data():
    """Factory fixture for creating mock stock data"""
    def _create(prices, dividends=None, dates=None):
        if dates is None:
            dates = pd.date_range('2024-01-01', periods=len(prices), freq='D')

        mock_ticker = MagicMock()
        hist = pd.DataFrame({
            'Close': prices,
            'Open': prices,
            'High': prices,
            'Low': prices,
            'Volume': [1000000] * len(prices)
        }, index=dates)
        hist.index = hist.index.strftime('%Y-%m-%d')

        mock_ticker.history.return_value = hist
        mock_ticker.dividends = dividends if dividends is not None else pd.Series(dtype=float)

        return mock_ticker
    return _create

# Then in tests (REMOVE 8 lines, ADD 1):
def test_something(mock_stock_data):
    with patch('app.yf.Ticker', return_value=mock_stock_data([100, 200, 300])):
        result = calculate_dca_core('AAPL', '2024-01-01', '2024-01-03', 100)
        assert result['total_return_percent'] > 0
```

### Option 2: Base Test Class with setUp (Current Pattern Improvement)
- **Pros**:
  - Works with existing unittest framework
  - No pytest migration needed
  - Inheritance-based reuse
- **Cons**:
  - Less flexible than fixtures
  - Still requires updating all test classes
  - Implicit dependencies (inheritance can hide logic)
- **Effort**: Medium (3-4 hours)
- **Risk**: Low

**Implementation**:
```python
# tests/base_test.py (NEW FILE)
import unittest
from unittest.mock import MagicMock, patch

class DCATestCase(unittest.TestCase):
    def setup_mock_stock(self, prices, dividends=None, dates=None):
        """Helper to create mock stock data"""
        # ... same logic as pytest fixture
        return mock_ticker

    def setUp(self):
        self.mock_ticker_patcher = patch('app.yf.Ticker')
        self.mock_ticker = self.mock_ticker_patcher.start()

    def tearDown(self):
        self.mock_ticker_patcher.stop()

# Then in tests:
class TestCalculations(DCATestCase):
    def test_something(self):
        self.mock_ticker.return_value = self.setup_mock_stock([100, 200, 300])
        # ... test logic
```

### Option 3: Helper Module (Minimal Change)
- **Pros**:
  - Smallest change to existing code
  - No framework migration
  - Works with current test structure
- **Cons**:
  - Still requires explicit import in every file
  - Less discoverable than fixtures
- **Effort**: Low (2 hours)
- **Risk**: Very Low

**Implementation**:
```python
# tests/helpers.py (NEW FILE)
def create_mock_stock_data(prices, dividends=None, dates=None):
    """Returns configured MagicMock for yfinance Ticker"""
    # ... setup logic
    return mock_ticker

# In tests (REMOVE 8 lines, ADD 2):
from tests.helpers import create_mock_stock_data

def test_something(self):
    mock_ticker = create_mock_stock_data([100, 200, 300])
    # ... use mock_ticker
```

## Recommended Action

**Implement Option 1 (pytest fixtures)** for long-term maintainability and test clarity.

**Migration Path**:
1. Create `tests/conftest.py` with fixtures
2. Migrate one test file as proof-of-concept
3. Update remaining 16 files incrementally
4. Delete redundant mock setup code (1,160 lines)

**Common Mock Scenarios to Support**:
- `basic_stock`: Flat $100 price, no dividends
- `trending_up`: Prices increasing 10% monthly
- `volatile`: Prices with 20% daily swings
- `with_dividends`: Quarterly $0.50 dividends
- `margin_call`: Price crash scenario (50% drop)

## Technical Details

**Affected Files**:
- `tests/conftest.py` - CREATE (central fixtures)
- 17 test files - MODIFY (remove setup, use fixtures)
- Total lines removed: ~1,160

**Fixture Design**:
```python
@pytest.fixture
def basic_stock():
    """100 days of $100 price, no dividends"""
    return mock_stock_data([100] * 100)

@pytest.fixture
def trending_stock():
    """Price increases from $100 to $200 over 100 days"""
    prices = [100 + i for i in range(100)]
    return mock_stock_data(prices)

@pytest.fixture
def dividend_stock():
    """Stock with quarterly dividends"""
    prices = [100] * 100
    dividends = pd.Series({
        '2024-03-15': 0.50,
        '2024-06-15': 0.50,
        '2024-09-15': 0.50,
    })
    return mock_stock_data(prices, dividends=dividends)
```

## Acceptance Criteria

- [ ] `tests/conftest.py` created with shared fixtures
- [ ] Common mock scenarios defined (basic, trending, volatile, dividend)
- [ ] All 145 duplicate mock setups replaced with fixture usage
- [ ] Test suite passes with 100% coverage maintained
- [ ] Test suite LOC reduced by ~1,000 lines
- [ ] Documentation added for how to use fixtures
- [ ] New test files use fixtures (not manual setup)

## Work Log

### 2025-11-29
- **Discovered**: Code Simplicity Reviewer found 145 instances of duplicated mock setup
- **Impact**: P1 - 10% of test suite is duplicate code
- **Measurement**: 1,160 lines across 17 files

## Resources

- [pytest Fixtures Documentation](https://docs.pytest.org/en/stable/fixture.html)
- [Refactoring Test Code](https://martinfowler.com/articles/refactoring-test-code.html)
- [DRY Principle in Testing](https://testing.googleblog.com/2019/12/testing-on-toilet-tests-too-dry-make.html)

---
status: pending
priority: p2
issue_id: 010
tags: [code-review, testing, refactoring, code-quality]
dependencies: [007]
---

# Continue Test Migration to conftest Helpers

## Problem Statement

We've started migrating tests to use shared `conftest.py` helpers but have 135 more test methods to migrate across 21 files. Completing this migration will remove **~1,100 lines** of duplicate mock setup code (80% reduction).

**Why it matters**: The test suite currently has 139 instances of identical mock setup code. Each time the yfinance API or mock structure changes, we need to update code in 139 places. This is error-prone, time-consuming, and violates DRY principles.

## Progress So Far

**Completed**:
- ✅ Created `tests/conftest.py` with 9 helper functions
- ✅ Migrated 4 test methods in `test_calculations.py` (33% of that file)
- ✅ Created comprehensive `TEST_MIGRATION_GUIDE.md`
- ✅ Verified all tests pass after migration

**Remaining**:
- 📋 8 more methods in `test_calculations.py`
- 📋 135 methods across 21 other test files

## Findings

**Source**: Code Simplicity Reviewer + Pattern Recognition Specialist

- **Location**: 22 test files
- **Duplicate Code**: 139 instances of 8-10 line mock setup
- **Total Lines**: ~1,390 lines of mock setup code
- **After Migration**: ~278 lines (using helpers)
- **Savings**: ~1,112 lines (80% reduction)

**Evidence**:
```bash
$ grep -h "mock_stock = MagicMock()" tests/test_*.py | wc -l
139
```

**Test Files Remaining**:
1. test_calculations.py (8 more)
2. test_financial_accuracy.py (~12 methods)
3. test_margin_trading.py (~15 methods)
4. test_withdrawal_edge_cases.py (~10 methods)
5. test_withdrawal_integration.py (~10 methods)
6. test_prd_compliance.py (~15 methods)
7. ... 16 more files

## Proposed Solutions

### Option 1: Incremental Migration (Recommended)
- **Pros**:
  - Low risk (small PRs, easy to review)
  - Can be done in spare time
  - Continuous delivery of value
  - Easy to pause/resume
- **Cons**:
  - Takes longer calendar time
  - Multiple PRs to track
- **Effort**: 4-6 hours total, spread across multiple sessions
- **Risk**: Very Low

**Implementation**:
- Batch 1 (1 hour): Finish test_calculations.py + test_financial_accuracy.py
- Batch 2 (1 hour): test_margin_trading.py + test_data_validation.py
- Batch 3 (1.5 hours): test_withdrawal_*.py files (3 files)
- Batch 4 (1.5 hours): Remaining high-value files

### Option 2: Automated Script Migration
- **Pros**:
  - Fast (all files in 30 minutes)
  - Consistent transformations
  - No manual tedium
- **Cons**:
  - Complex edge cases may break
  - Requires careful script writing
  - Need manual review of all changes
- **Effort**: High (2-3 hours to write script + 1 hour to review/fix)
- **Risk**: Medium

**Implementation**:
```python
# migration_script.py
import re

def migrate_test_file(filepath):
    # Regex to find mock setup pattern
    # Replace with create_mock_stock_data() call
    # Handle edge cases (dividends, side effects, etc.)
    ...
```

### Option 3: Do All Manually in One Session
- **Pros**:
  - Complete control
  - Can handle edge cases
  - Single PR
- **Cons**:
  - Very time-consuming (5-6 hours)
  - High token usage
  - Tedious and error-prone
- **Effort**: Very High (5-6 hours non-stop)
- **Risk**: Low (but exhausting)

## Recommended Action

**Implement Option 1 (Incremental Migration)** - do 1-2 batches per session

**Session 1** (DONE):
- ✅ Create conftest.py
- ✅ Migrate 4 methods in test_calculations.py
- ✅ Create migration guide

**Session 2** (Next):
- [ ] Complete test_calculations.py (8 more methods)
- [ ] Migrate test_financial_accuracy.py (~12 methods)
- [ ] Create PR for Batch 1

**Session 3**:
- [ ] Migrate test_margin_trading.py (~15 methods)
- [ ] Migrate test_data_validation.py (~8 methods)
- [ ] Create PR for Batch 2

**Session 4**:
- [ ] Migrate test_withdrawal_*.py files (3 files, ~30 methods)
- [ ] Create PR for Batch 3

**Session 5**:
- [ ] Migrate remaining 16 files (~60 methods)
- [ ] Create final PR for Batch 4

## Technical Details

**Affected Files**:
- 22 test files in `tests/` directory
- `TEST_MIGRATION_GUIDE.md` - comprehensive guide (new)

**Migration Pattern** (from guide):
```python
# BEFORE (8-10 lines)
mock_stock = MagicMock()
dates = pd.date_range(start='2023-01-01', periods=3, freq='D')
data = {'Close': [100.0, 200.0, 300.0]}
hist = pd.DataFrame(data, index=dates)
mock_stock.history.return_value = hist
mock_stock.dividends = pd.Series(dtype=float)
mock_ticker.return_value = mock_stock

# AFTER (1 line)
mock_ticker.return_value = create_mock_stock_data([100.0, 200.0, 300.0], start_date='2023-01-01')
```

**Testing Strategy**:
- Run `python -m unittest tests.test_<filename>` after each file
- Run full suite after each batch: `python -m unittest discover tests/`
- Ensure 100% test pass rate maintained

## Acceptance Criteria

**Per Batch**:
- [ ] 20-30 test methods migrated
- [ ] All tests in migrated files pass
- [ ] Code reduction metrics calculated
- [ ] PR created with before/after comparison

**Final Completion**:
- [ ] All 139 mock setup instances replaced with helpers
- [ ] ~1,100 lines of duplicate code removed
- [ ] Full test suite passes: `python -m unittest discover tests/`
- [ ] No test failures introduced
- [ ] TEST_MIGRATION_GUIDE.md updated with completion status

## Work Log

### 2025-11-29 - Session 1
- **Created**: tests/conftest.py with 9 helper functions
- **Migrated**: 4 test methods in test_calculations.py
  - test_calculate_dca_no_dividends
  - test_calculate_dca_with_dividends
  - test_calculate_dca_with_initial_investment
  - test_calculate_dca_with_benchmark
- **Lines Removed**: ~32 lines (8 lines × 4 tests)
- **Impact**: 4/139 complete (3%)
- **Created**: TEST_MIGRATION_GUIDE.md (comprehensive migration documentation)
- **Status**: Foundation complete, ready for incremental batch migration

## Resources

- [TEST_MIGRATION_GUIDE.md](../TEST_MIGRATION_GUIDE.md) - Complete migration guide
- [tests/conftest.py](../tests/conftest.py) - Shared helper functions
- [todo 007](007-pending-p1-test-mock-duplication.md) - Original finding
- [pytest fixtures documentation](https://docs.pytest.org/en/stable/fixture.html)

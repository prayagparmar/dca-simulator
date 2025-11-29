---
status: pending
priority: p1
issue_id: 006
tags: [code-review, architecture, refactoring, maintainability]
dependencies: []
---

# God Object: calculate_dca_core() Function Too Large

## Problem Statement

The `calculate_dca_core()` function is 532 lines (27% of app.py), handles 7 distinct concerns, manages 40+ local variables, and contains 123 control flow statements. This violates the Single Responsibility Principle and makes the code extremely difficult to understand, test, and modify.

**Why it matters**: Every new feature (withdrawal mode, margin trading, dividend reinvestment) adds complexity to this single function. Future changes risk breaking existing functionality. New developers need to understand 532 lines of sequential logic to make any modifications.

## Findings

**Source**: Architecture Strategist + Pattern Recognition Specialist + Code Simplicity Reviewer

- **Location**: `/Users/prayagparmar/Downloads/finance/app.py:1285-1814` (532 lines)
- **Complexity Metrics**:
  - **Lines**: 532 (should be <100)
  - **Parameters**: 13 (should be <5)
  - **Local variables**: 40+ (should be <10)
  - **Control flow**: 123 conditionals/loops (should be <20)
  - **Concerns**: 7 different responsibilities (should be 1)
- **Responsibilities Mixed**:
  1. Data fetching and preparation (lines 1286-1299)
  2. State initialization (43 variables, lines 1302-1362)
  3. Margin requirement checking (lines 1389-1442)
  4. Insolvency detection (lines 1447-1486)
  5. Withdrawal processing (lines 1492-1566)
  6. Dividend reinvestment (lines 1568-1591)
  7. Daily purchase execution (lines 1597-1663)
  8. Analytics calculation (lines 1715-1742)
  9. Result formatting (lines 1744-1814)

**Evidence of Complexity**:
```python
# Function signature with 13 parameters:
def calculate_dca_core(
    ticker, start_date, end_date, amount, initial_amount=0,
    reinvest=False, target_dates=None, account_balance=None,
    margin_ratio=NO_MARGIN_RATIO, maintenance_margin=DEFAULT_MAINTENANCE_MARGIN,
    withdrawal_threshold=None, monthly_withdrawal_amount=0.0, frequency='DAILY'
):
    # 532 lines of nested logic...
```

## Proposed Solutions

### Option 1: Extract to SimulationEngine Class (Recommended)
- **Pros**:
  - Clear separation of concerns
  - State encapsulated in class
  - Each method <100 lines
  - Easier to test individual components
  - Enables future features (e.g., pause/resume simulation)
- **Cons**:
  - Requires larger refactoring effort
  - Tests need updating
- **Effort**: High (1-2 days)
- **Risk**: Medium (requires comprehensive testing)

**Implementation**:
```python
class SimulationEngine:
    def __init__(self, ticker, start_date, end_date, params):
        self.ticker = ticker
        self.dates = None
        self.portfolio = PortfolioState()  # Encapsulate state
        self.params = SimulationParams(**params)

    def run(self):
        """Orchestrator method - delegates to specialized handlers"""
        self._fetch_data()
        self._initialize_portfolio()

        for date, row in self.data.iterrows():
            self._process_trading_day(date, row)

        return self._build_results()

    def _process_trading_day(self, date, row):
        """Single day iteration - easier to understand"""
        self._check_margin_requirements(date, row)
        self._check_insolvency(date)
        self._process_withdrawals(date, row)
        self._process_dividends(date, row)
        self._charge_interest(date)
        self._execute_purchase(date, row)
        self._record_metrics(date, row)

    # Each method: 20-50 lines, single responsibility

# Usage:
def calculate_dca_core(...):
    engine = SimulationEngine(ticker, start_date, end_date, {
        'amount': amount,
        'initial_amount': initial_amount,
        # ... other params
    })
    return engine.run()
```

### Option 2: Extract Helper Functions (Incremental)
- **Pros**:
  - Smaller, incremental changes
  - Less risky than full class refactor
  - Can be done in phases
- **Cons**:
  - Still passes many parameters
  - Doesn't solve state management issue
  - Intermediate improvement only
- **Effort**: Medium (3-4 hours)
- **Risk**: Low

**Implementation** (Phase 1):
```python
def calculate_dca_core(...):
    hist, dividends = fetch_and_prepare_data(ticker, start_date, end_date)
    state = initialize_simulation_state(account_balance, margin_ratio, ...)

    for date, row in hist.iterrows():
        state = process_single_day(date, row, state, params)

    return format_results(state)

def process_single_day(date, row, state, params):
    """Extract the 300-line loop body"""
    state = check_margin_requirements(date, row, state)
    state = check_insolvency(date, state)
    state = process_withdrawals(date, row, state, params)
    # ... etc
    return state
```

### Option 3: Do Nothing (Not Recommended)
- **Pros**: No effort required
- **Cons**:
  - Complexity will continue to grow
  - Each new feature makes it worse
  - Risk of bugs increases
  - Onboarding new developers is painful
- **Effort**: Zero
- **Risk**: High (technical debt compounds)

## Recommended Action

**Implement Option 2 (Extract Helper Functions) immediately** as a stepping stone, then plan Option 1 (SimulationEngine class) for next major version.

**Phase 1 (Immediate)**:
1. Extract `process_single_day()` - moves 300 lines out of main function
2. Extract `build_results()` - separates analytics from simulation
3. Extract `initialize_state()` - clarifies startup logic

**Phase 2 (Next Quarter)**:
- Full SimulationEngine class refactor
- PortfolioState dataclass for state management
- SimulationParams dataclass for configuration

## Technical Details

**Affected Files**:
- `app.py` - refactor calculate_dca_core()
- All 30 test files - update to use new structure
- `tests/test_simulation_engine.py` - new unit tests for engine

**Breaking Changes**: None (external API stays the same)

**State Management**:
Current: 40+ local variables scattered throughout function
Proposed: Encapsulated in PortfolioState dataclass

```python
@dataclass
class PortfolioState:
    total_shares: float = 0.0
    total_cost_basis: float = 0.0
    borrowed_amount: float = 0.0
    current_balance: float = 0.0
    # ... 36 more fields
```

## Acceptance Criteria

**Phase 1 (Helper Functions)**:
- [ ] `process_single_day()` function extracted (handles one day's logic)
- [ ] `build_results()` function extracted (analytics + formatting)
- [ ] Main function reduced from 532 to <150 lines
- [ ] All existing tests pass without modification
- [ ] Code coverage maintained at 75%+

**Phase 2 (Class Refactor)**:
- [ ] SimulationEngine class created
- [ ] PortfolioState and SimulationParams dataclasses defined
- [ ] Each method <100 lines
- [ ] Unit tests for each method
- [ ] Integration tests for full simulation

## Work Log

### 2025-11-29
- **Discovered**: Multiple agents (Architecture, Pattern, Simplicity) identified God Object
- **Impact**: P1 - Blocks future feature development and maintainability
- **Metrics**: 532 lines, 13 params, 40+ variables, 123 control statements

## Resources

- [Refactoring Guru: Extract Method](https://refactoring.guru/extract-method)
- [Martin Fowler: Long Method Code Smell](https://refactoring.com/catalog/extractFunction.html)
- [Python Dataclasses](https://docs.python.org/3/library/dataclasses.html)
- Similar refactor in [open-source project](https://github.com/search?q=SimulationEngine+python)

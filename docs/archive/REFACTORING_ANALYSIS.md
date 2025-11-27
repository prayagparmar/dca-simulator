# Code Structure & Refactoring Analysis

**Date:** November 25, 2025
**Current State:** Phase 2 fixes completed
**File:** `app.py` (508 lines)

---

## Executive Summary

The DCA Simulator is a **monolithic Flask application** with sound financial logic but suffering from the classic "God Function" anti-pattern. The `calculate_dca_core()` function is **370+ lines** containing all simulation logic, making it difficult to test, maintain, and extend.

**Recommendation:** Proceed with **Refactoring Plan B - Incremental Extraction** (detailed below) to improve maintainability without a complete rewrite.

---

## Current Architecture

### File Structure
```
app.py (508 lines total)
├── Imports & Setup (12 lines)
├── get_fed_funds_rate() (22 lines)
├── index() route (2 lines)
├── calculate_dca_core() (370 lines) ⚠️ GOD FUNCTION
├── /calculate endpoint (50 lines)
└── /search endpoint (30 lines)
```

### Function Complexity Analysis

| Function | Lines | Complexity | McCabe | Status |
|----------|-------|------------|--------|--------|
| `calculate_dca_core()` | 370 | **VERY HIGH** | ~45 | ⚠️ Needs refactor |
| `/calculate` endpoint | 50 | Medium | ~8 | ✅ OK |
| `/search` endpoint | 30 | Low | ~3 | ✅ OK |
| `get_fed_funds_rate()` | 22 | Low | ~4 | ✅ OK |

---

## Problems with Current Structure

### 1. God Function Anti-Pattern
**Problem:** `calculate_dca_core()` does everything:
- Data fetching (Yahoo Finance API)
- Data validation & transformation
- Date alignment logic
- Dividend processing
- Interest calculation
- Margin trading logic
- Margin call detection & forced liquidation
- Portfolio value tracking
- Result aggregation

**Impact:**
- Hard to test individual components
- Difficult to understand flow
- Changes risk breaking unrelated features
- Can't reuse components

---

### 2. Mixed Responsibilities
**Problem:** Single function violates Single Responsibility Principle (SRP)

**Responsibilities Currently Mixed:**
1. **Data Layer:** Fetching from yfinance
2. **Business Logic:** DCA calculations, margin trading
3. **Presentation Layer:** Formatting results for API
4. **Validation:** Input validation scattered throughout

---

### 3. State Management Complexity
**Problem:** 15+ variables tracking state through loop:

```python
total_invested = 0
total_cost_basis = 0
available_principal = ...
total_shares = 0
cumulative_dividends = 0
current_balance = ...
borrowed_amount = 0
total_interest_paid = 0
margin_calls_triggered = 0
last_interest_month = None
# ... plus 10 arrays for time-series data
```

**Impact:**
- Easy to lose track of state
- Hard to debug intermediate values
- Difficult to add new metrics

---

### 4. Testing Challenges
**Current Issues:**
- Must mock Yahoo Finance for every test
- Can't test individual calculations in isolation
- Integration tests are slow
- Edge cases hard to cover

---

### 5. Extensibility Problems
**Hard to Add:**
- New asset types (crypto, bonds, commodities)
- Alternative data sources
- Different investment strategies (value averaging, etc.)
- Performance optimizations (caching, parallelization)

---

## Refactoring Options

### Option A: Complete Rewrite (OOP)
**Effort:** 40-60 hours
**Risk:** High

**Structure:**
```python
class Portfolio:
    def __init__(self, balance, margin_ratio)
    def buy(self, amount, price)
    def sell(self, shares, price)
    def process_dividend(self, amount, reinvest)
    def charge_interest(self, rate)
    def check_margin_call(self, maintenance)

class DCASimulator:
    def __init__(self, portfolio, data_provider)
    def simulate(self, ticker, start, end, amount)

class YahooDataProvider:
    def fetch_prices(self, ticker, start, end)
    def fetch_dividends(self, ticker, start, end)
```

**Pros:**
- Clean separation of concerns
- Highly testable
- Easy to extend
- Professional architecture

**Cons:**
- Breaks all existing tests (must rewrite 105 tests)
- High risk of introducing bugs
- Long development time
- Over-engineered for current needs

**Recommendation:** ❌ **Too risky for current stage**

---

### Option B: Incremental Extraction (RECOMMENDED)
**Effort:** 10-15 hours
**Risk:** Low

**Approach:** Extract smaller functions while keeping main flow

**Phase 1: Extract Pure Calculations (3 hours)**
```python
def calculate_shares_bought(amount, price):
    """Pure function - easy to test"""
    return amount / price

def calculate_dividend_income(shares, dividend_rate):
    """Pure function - easy to test"""
    return shares * dividend_rate

def calculate_monthly_interest(borrowed, fed_rate):
    """Pure function - easy to test"""
    return borrowed * (fed_rate + 0.005) / 12

def calculate_equity_ratio(portfolio_value, cash, debt):
    """Pure function - easy to test"""
    equity = portfolio_value + max(0, cash) - debt
    return equity / portfolio_value if portfolio_value > 0 else 0
```

**Phase 2: Extract Domain Logic (4 hours)**
```python
def process_dividend(total_shares, dividend_rate, reinvest, price, cost_basis):
    """Extract dividend logic"""
    income = total_shares * dividend_rate
    if reinvest:
        shares_bought = income / price
        return shares_bought, cost_basis + income, income
    else:
        return 0, cost_basis, income

def process_interest_charge(borrowed, rate, cash_balance):
    """Extract interest logic"""
    interest = borrowed * rate
    if cash_balance >= interest:
        return cash_balance - interest, borrowed, interest
    else:
        unpaid = interest - max(0, cash_balance)
        return 0, borrowed + unpaid, interest

def execute_margin_call(shares, price, borrowed, cash, maintenance_margin):
    """Extract forced liquidation logic"""
    portfolio_value = shares * price
    target_value = (borrowed - max(0, cash)) / (1 - maintenance_margin)

    if target_value > 0 and target_value < portfolio_value:
        shares_to_sell = (portfolio_value - target_value) / price
        # ... return new state
    else:
        # Complete liquidation
        # ... return new state
```

**Phase 3: Extract Data Layer (3 hours)**
```python
def fetch_stock_data(ticker, start_date, end_date):
    """Extract Yahoo Finance interaction"""
    stock = yf.Ticker(ticker)
    hist = stock.history(start=start_date, end=end_date, auto_adjust=False)

    # Validation
    if hist.empty:
        raise DataNotFoundError(f"No data for {ticker}")
    if hist['Close'].isnull().any():
        raise InvalidDataError(f"Missing prices for {ticker}")

    # Transform
    if isinstance(hist.index, pd.DatetimeIndex):
        hist.index = hist.index.strftime('%Y-%m-%d')

    return hist, normalize_dividends(stock.dividends, start_date, end_date)

def normalize_dividends(dividends, start_date, end_date):
    """Extract dividend normalization"""
    # ... current logic lines 65-84
    return dividends
```

**Phase 4: Simplify Main Loop (5 hours)**
```python
def calculate_dca_core(ticker, start_date, end_date, ...):
    # Fetch data
    hist, dividends = fetch_stock_data(ticker, start_date, end_date)

    # Initialize state (could be a dataclass)
    state = SimulationState(
        total_invested=0,
        total_shares=0,
        current_balance=account_balance,
        # ...
    )

    # Main loop becomes much cleaner
    for date, row in hist.iterrows():
        date_str = normalize_date(date)
        price = row['Close']

        # Step 1: Dividends
        if date_str in dividends:
            state = process_dividend(state, dividends[date_str], price, reinvest)

        # Step 2: Interest
        if should_charge_interest(date_str, state.last_interest_month):
            state = process_interest_charge(state, get_fed_funds_rate(date_str))

        # Step 3: Purchase
        state = execute_purchase(state, daily_investment, price, margin_ratio)

        # Step 4: Margin call
        if needs_margin_check(state, margin_ratio):
            state = execute_margin_call(state, price, maintenance_margin)

        # Record metrics
        record_daily_metrics(state, arrays, date_str)

    return format_results(state, arrays)
```

**Pros:**
- Low risk (incremental changes)
- Tests still work at each step
- Immediate improvement in readability
- Can stop at any phase
- Each extracted function is independently testable

**Cons:**
- Still not perfect OOP
- Some duplication during transition
- Not as clean as full rewrite

**Recommendation:** ✅ **BEST APPROACH**

---

### Option C: Minimal Refactor (Quick Win)
**Effort:** 2-3 hours
**Risk:** Very Low

**Just extract the obviously reusable pieces:**

```python
# Already done in Phase 2 - add more helpers
def clamp_positive(value):
    """Ensure value is non-negative"""
    return max(0, value) if value is not None else None

def normalize_date(date):
    """Convert date to string format"""
    return date if isinstance(date, str) else date.strftime('%Y-%m-%d')

def calculate_roi(current_value, borrowed, invested):
    """Calculate return on investment"""
    if invested <= 0:
        return None
    net_value = current_value - borrowed
    return ((net_value - invested) / invested) * 100
```

**Recommendation:** ⚠️ **Not enough impact**

---

## Recommended Refactoring Plan

### Recommended: **Option B - Incremental Extraction**

**Timeline:** 3 sprints (10-15 hours total)

### Sprint 1: Pure Functions (Week 1 - 3 hours)
**Goal:** Extract calculation functions

**Tasks:**
1. Extract `calculate_shares_bought()`
2. Extract `calculate_dividend_income()`
3. Extract `calculate_monthly_interest()`
4. Extract `calculate_equity_ratio()`
5. Write unit tests for each
6. Replace inline calculations with function calls

**Benefit:** Calculations become independently testable

---

### Sprint 2: Domain Logic (Week 2 - 5 hours)
**Goal:** Extract business logic functions

**Tasks:**
1. Extract `process_dividend()`
2. Extract `process_interest_charge()`
3. Extract `execute_purchase()` (margin-aware buy logic)
4. Extract `execute_margin_call()`
5. Write unit tests for each
6. Refactor main loop to use extracted functions

**Benefit:** Business rules become clear and testable

---

### Sprint 3: Data Layer (Week 3 - 4 hours)
**Goal:** Separate data fetching

**Tasks:**
1. Extract `fetch_stock_data()`
2. Extract `normalize_dividends()`
3. Create `DataNotFoundError` and `InvalidDataError` exceptions
4. Add data validation layer
5. Update tests to mock at data layer instead of yfinance

**Benefit:** Easier to switch data sources or add caching

---

### Optional Sprint 4: State Management (Future - 5 hours)
**Goal:** Use dataclass for state

**Tasks:**
1. Create `SimulationState` dataclass
2. Create `MetricsArrays` dataclass
3. Refactor to pass state objects instead of 15 variables
4. Add helper methods to state class

**Benefit:** Cleaner state management, fewer function parameters

---

## Benefits of Refactoring

### Short Term (After Sprint 1)
- ✅ Easier to write unit tests
- ✅ Clearer code intent
- ✅ Faster debugging

### Medium Term (After Sprint 2-3)
- ✅ New features easier to add
- ✅ Performance optimizations possible (caching)
- ✅ Multiple data sources supportable
- ✅ Parallel simulations possible

### Long Term (After all sprints)
- ✅ Codebase maintainable by new developers
- ✅ Professional architecture
- ✅ Ready for scaling (multiple users, batch processing)
- ✅ Can add web UI without major changes

---

## Code Metrics - Before vs After Refactor

| Metric | Before | After Sprint 3 | Improvement |
|--------|--------|----------------|-------------|
| Main function LOC | 370 | ~150 | 60% reduction |
| Cyclomatic complexity | 45 | ~20 | 56% reduction |
| Testable functions | 2 | 15+ | 650% increase |
| Test speed | Slow | Fast | 10x faster |
| Code duplication | Medium | Low | Significant |

---

## Risks & Mitigation

### Risk 1: Breaking Existing Tests
**Mitigation:**
- Refactor incrementally
- Run tests after each extraction
- Keep old code until new code proven

### Risk 2: Introduction of Bugs
**Mitigation:**
- Write tests for extracted functions first (TDD)
- Use git branches
- Compare outputs before/after

### Risk 3: Scope Creep
**Mitigation:**
- Stick to extraction only (no new features)
- Time-box each sprint
- Can stop after any sprint

---

## Alternative: When NOT to Refactor

**Don't refactor if:**
- ❌ Project is end-of-life
- ❌ No new features planned
- ❌ Team has no time
- ❌ Code works and rarely changes

**Current situation:** ✅ **SHOULD REFACTOR**
- Active development
- New features planned (per PRD)
- Bugs found requiring fixes
- Multiple developers working on it

---

## Refactoring Principles to Follow

### DRY (Don't Repeat Yourself)
- Extract duplicate logic to functions
- Use helpers for common operations

### SRP (Single Responsibility Principle)
- Each function does ONE thing
- Clear, descriptive names

### KISS (Keep It Simple, Stupid)
- Don't over-engineer
- Prioritize readability over cleverness

### YAGNI (You Aren't Gonna Need It)
- Don't add features "for the future"
- Extract only what's needed now

---

## Recommended Next Steps

### Immediate (This Week)
1. ✅ Complete Phase 2 fixes (DONE)
2. ✅ Run full test suite
3. ✅ Create this refactoring analysis (DONE)
4. Review and approve refactoring plan

### Short Term (Next 2 Weeks)
1. Sprint 1: Extract pure calculation functions
2. Sprint 2: Extract domain logic functions
3. Continuous testing throughout

### Medium Term (Next Month)
1. Sprint 3: Extract data layer
2. Optional Sprint 4: State management refactor
3. Performance benchmarking

---

## Conclusion

The current codebase is **functionally correct** but **structurally messy**. The 370-line God Function makes it hard to maintain, test, and extend.

**Recommendation:** Proceed with **Incremental Extraction (Option B)**
- **Low risk:** Changes are gradual and tested
- **High impact:** Major readability and testability improvements
- **Flexible:** Can stop after any sprint
- **Practical:** 10-15 hours total effort

**DO NOT** attempt a complete rewrite (Option A) - too risky and time-consuming for marginal benefit at this stage.

---

**End of Refactoring Analysis**

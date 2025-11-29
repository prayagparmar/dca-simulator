---
status: pending
priority: p2
issue_id: 008
tags: [code-review, data-integrity, input-validation]
dependencies: []
---

# No Validation for Negative Investment Amounts

## Problem Statement

The `/calculate` endpoint validates `amount < 0` but doesn't validate `initial_amount < 0`. Additionally, `calculate_dca_core()` can be called programmatically with negative values, creating negative shares and corrupting portfolio calculations.

**Why it matters**: Negative amounts invert portfolio logic, creating nonsensical results. While the Flask endpoint validates `amount`, direct calls to `calculate_dca_core()` (e.g., from tests or future refactors) could bypass validation and corrupt financial calculations.

## Findings

**Source**: Data Integrity Guardian

- **Location**: `/Users/prayagparmar/Downloads/finance/app.py:1849-1850, 1821`
- **Validation Gaps**:
  - `amount` validated at line 1849-1850 ✅
  - `initial_amount` NOT validated ❌
  - No validation in `calculate_dca_core()` itself ❌
- **Evidence**:
  ```python
  # Line 1849-1850: amount validated
  if amount < 0:
      return jsonify({'error': 'Daily investment amount must be non-negative'}), 400

  # Line 1852: initial_amount NOT validated
  initial_amount = float(data.get('initial_amount', 0))

  # calculate_dca_core() trusts inputs completely
  ```

**Test Evidence** (test_comprehensive_flaws.py:608-624):
```python
result = calculate_dca_core(
    ticker='TEST',
    start_date='2024-01-01',
    end_date='2024-01-01',
    amount=-100,  # Negative investment (selling?)
    initial_amount=0,
    reinvest=False
)
# Code doesn't validate - POTENTIAL BUG
```

**Risk Scenario**:
```python
# Negative amount creates negative shares:
shares_bought = calculate_shares_bought(-100, 25)  # Returns -4 shares
total_shares += (-4)  # Now negative!
portfolio_value = total_shares * price  # Now negative!
```

## Proposed Solutions

### Option 1: Validation in Both Endpoint and Core Function (Recommended)
- **Pros**:
  - Defense in depth (two validation layers)
  - Protects against programmatic calls
  - Clear error messages at each layer
- **Cons**:
  - Slight code duplication (validation in 2 places)
- **Effort**: Low (30 minutes)
- **Risk**: Very Low

**Implementation**:
```python
# In /calculate endpoint (ADD initial_amount validation):
if initial_amount < 0:
    return jsonify({'error': 'Initial investment must be non-negative'}), 400

# In calculate_dca_core() (ADD defensive validation):
def calculate_dca_core(ticker, start_date, end_date, amount, initial_amount=0, ...):
    # Defensive validation (protect against programmatic misuse)
    if amount < 0:
        raise ValueError(f"amount must be non-negative, got {amount}")
    if initial_amount < 0:
        raise ValueError(f"initial_amount must be non-negative, got {initial_amount}")

    # ... rest of function
```

### Option 2: Endpoint Validation Only
- **Pros**:
  - Single validation point
  - No code duplication
- **Cons**:
  - Programmatic calls bypass validation
  - Future refactors could introduce bugs
- **Effort**: Very Low (10 minutes)
- **Risk**: Medium

**Implementation**:
```python
# Just add to /calculate endpoint:
if initial_amount < 0:
    return jsonify({'error': 'Initial investment must be non-negative'}), 400
```

### Option 3: Pydantic Data Validation (Future-Proof)
- **Pros**:
  - Type safety and validation in one
  - Auto-generated API documentation
  - Catches many input errors automatically
- **Cons**:
  - Adds dependency
  - Requires larger refactor
- **Effort**: High (3-4 hours)
- **Risk**: Low

**Implementation**:
```python
from pydantic import BaseModel, Field

class SimulationRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    start_date: str
    end_date: str
    amount: float = Field(..., ge=0)  # >= 0
    initial_amount: float = Field(0, ge=0)
    # ... other fields

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        params = SimulationRequest(**request.json)
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
```

## Recommended Action

**Implement Option 1 immediately** - add validation to both endpoint and core function for defense in depth.

**Additional Validations to Add**:
- `amount >= 0` ✅ (already done)
- `initial_amount >= 0` ❌ (missing)
- `margin_ratio >= 1.0` ✅ (already done)
- `maintenance_margin >= 0 and <= 1.0` ❌ (missing)
- `withdrawal_threshold >= 0` ✅ (already done)
- `monthly_withdrawal_amount >= 0` ❌ (missing)

## Technical Details

**Affected Files**:
- `app.py` - add validation to endpoint and core function
- `tests/test_input_validation.py` - add test cases

**Error Messages**:
- Endpoint: Return 400 with clear JSON error
- Core function: Raise ValueError with descriptive message

**Edge Cases to Test**:
- `amount = -100`: Should reject
- `initial_amount = -1000`: Should reject
- `amount = 0, initial_amount = 0`: Valid (no investment)
- `amount = 0.01`: Valid (tiny investment)

## Acceptance Criteria

- [ ] `initial_amount < 0` validation added to `/calculate` endpoint
- [ ] Defensive validation added to `calculate_dca_core()` for all numeric inputs
- [ ] Test coverage for negative inputs:
  - [ ] Negative amount returns 400
  - [ ] Negative initial_amount returns 400
  - [ ] Negative monthly_withdrawal_amount returns 400
- [ ] ValueError raised with clear message for programmatic calls
- [ ] Edge case tests (zero values, very small values)

## Work Log

### 2025-11-29
- **Discovered**: Data Integrity Guardian found missing validation for `initial_amount`
- **Impact**: P2 - Could corrupt calculations if called programmatically
- **Evidence**: Test file showed negative amount scenario not validated

## Resources

- [Input Validation Best Practices](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Python ValueError](https://docs.python.org/3/library/exceptions.html#ValueError)

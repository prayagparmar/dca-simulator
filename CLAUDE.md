# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DCA (Dollar Cost Averaging) Simulator - A Flask web application that simulates investment strategies with advanced features including dividend reinvestment, margin trading, and benchmark comparisons. The app fetches real historical stock data from Yahoo Finance and simulates day-by-day investment scenarios.

## Commands

### Setup and Installation
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Start Flask development server
python app.py

# Application runs on http://localhost:8080
```

### Testing
```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_prd_compliance.py

# Run with verbose output
python -m pytest -v tests/

# Run specific test function
python -m pytest tests/test_calculations.py::TestCalculations::test_basic_dca
```

## Architecture

### Core Components

**Backend (app.py)**
- Single-file Flask application containing all backend logic
- `calculate_dca_core()`: Main simulation engine that processes day-by-day investments
- `/calculate` endpoint: Handles simulation requests and returns JSON results
- `/search` endpoint: Provides ticker autocomplete via Yahoo Finance API
- Fed Funds rate data loaded from `FEDFUNDS.csv` for margin interest calculations

**Frontend**
- `templates/index.html`: Single-page application with form inputs and results display
- `static/script.js`: Handles autocomplete, number formatting, form submission, and Chart.js visualization
- `static/style.css`: Dark mode UI with vibrant accent colors

### Simulation Flow

The `calculate_dca_core()` function is the heart of the application:

1. **Data Fetching**: Downloads historical price and dividend data using `yfinance` with `auto_adjust=False` (critical for preventing dividend double-counting)
2. **Day-by-Day Iteration**: Loops through each trading day in chronological order
3. **Daily Operations** (in order):
   - Process dividends (reinvest as shares OR add to cash balance)
   - Charge monthly interest on margin debt (first day of each month)
   - Execute daily investment (from cash, then margin if enabled and cash depleted)
   - Check margin call conditions and force liquidation if equity ratio < maintenance margin
   - Record all metrics for charting
4. **Return Results**: Summary statistics and time-series arrays for visualization

### Critical Financial Concepts

**Investment Accounting**
- `total_invested`: User's principal contribution only (excludes recycled dividends and margin)
- `total_cost_basis`: All money spent on shares (Principal + Dividends + Margin)
- `average_cost`: `total_cost_basis / total_shares` - true average price paid per share
- `available_principal`: Tracks remaining user capital vs recycled dividends

**Price Data Handling**
- Uses `auto_adjust=False` to fetch raw (unadjusted) prices from Yahoo Finance
- Stock prices naturally drop on ex-dividend dates, reflecting real market behavior
- Manual dividend reinvestment prevents double-counting that would occur with adjusted prices

**Margin Trading Logic**
- Conservative approach: margin only used when cash depletes (not pre-borrowed)
- Interest rate: Fed Funds Rate + 0.5%, charged monthly
- Interest paid from cash first, then capitalized to debt if insufficient cash
- Margin calls trigger forced liquidation to restore equity to exactly maintenance margin (25%)
- Leverage ratio: `portfolio_value / equity`

**Benchmark Alignment**
- Benchmark simulations use `target_dates` from main ticker to ensure identical trading days
- Forward-fill then back-fill to handle weekends/holidays and align dates perfectly
- Same investment parameters applied to benchmark for fair comparison

## File Organization

```
/
├── app.py                          # Flask backend (main simulation logic)
├── requirements.txt                # Python dependencies
├── FEDFUNDS.csv                   # Fed Funds rate data for margin interest
├── PRD.md                         # Product Requirements Document
├── TDD_COMPLIANCE_REPORT.md       # Test compliance documentation
├── TEST_COVERAGE_SUMMARY.md       # Test coverage metrics
├── templates/
│   └── index.html                 # Frontend UI
├── static/
│   ├── script.js                  # Frontend logic and Chart.js
│   └── style.css                  # Styling
└── tests/                         # Test suite (75+ tests)
    ├── test_prd_compliance.py     # PRD feature compliance
    ├── test_calculations.py       # Mathematical accuracy
    ├── test_margin_trading.py     # Margin logic
    ├── test_financial_accuracy.py # Financial calculations
    ├── test_edge_cases.py         # Edge cases
    ├── test_bdd_scenarios.py      # Behavior-driven scenarios
    ├── test_data_validation.py    # Input validation
    └── test_consistency_and_avg_cost.py  # Consistency checks

```

## Testing Strategy

The codebase has comprehensive test coverage (75+ tests) organized by concern:

- Tests use `unittest.mock.patch` to mock `yfinance` data fetching
- Helper function `setup_mock_data()` creates predictable price/dividend scenarios
- Tests verify exact numerical outputs for known inputs
- Edge cases include missing data, zero balances, extreme leverage, and forced liquidations

When modifying `calculate_dca_core()`, always run the full test suite to ensure no regressions.

## Key Implementation Notes

### Dividend Handling
When dividends are received:
- **Reinvest ON**: Immediately purchase shares at current price, add dividend amount to `total_cost_basis`
- **Reinvest OFF**: Add dividend to `current_balance` (liquid cash), can fund future investments

### Margin Trading
The margin implementation mimics Robinhood's behavior:
- Only borrows when cash depletes (doesn't pre-borrow to maximize leverage)
- Monthly interest charges compound if unpaid
- Forced liquidation sells exact number of shares to restore equity to 25%
- Tracks `borrowed_amount`, `total_interest_paid`, `margin_calls_triggered`

### Date Alignment for Benchmarks
Benchmarks must trade on identical days as the main ticker:
- Pass `target_dates` from main result to `calculate_dca_core()` for benchmark
- Function reindexes benchmark data to match target dates exactly
- Forward-fill handles weekends/holidays (use last known price)
- Back-fill handles initial missing data

### Common Gotchas
1. **Dividend Double-Counting**: Always use `auto_adjust=False` when fetching prices
2. **Date Format Consistency**: Convert all date indices to string format `'YYYY-MM-DD'`
3. **Principal vs Cost Basis**: `total_invested` ≠ `total_cost_basis` when dividends reinvested or margin used
4. **Margin Interest Timing**: Charge interest BEFORE daily investment, not after
5. **Forced Liquidation**: Target exactly 25% equity ratio, not above it

## Development Workflow

1. Read PRD.md to understand feature requirements
2. Write tests first (TDD approach)
3. Implement feature in `calculate_dca_core()` or add new endpoint
4. Run test suite to verify correctness
5. Test manually in browser at http://localhost:8080
6. Update documentation if architectural changes made

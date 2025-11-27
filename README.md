# DCA Simulator

A Flask-based Dollar Cost Averaging investment simulator with advanced features including dividend reinvestment, margin trading, comprehensive analytics, and benchmark comparisons.

## 🚀 Quick Start

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
python app.py
# Visit http://localhost:8080
```

## ✨ Features

- **Dollar Cost Averaging** - Simulate daily/periodic investments over time
- **Dividend Management** - Reinvestment or cash accumulation
- **Margin Trading** - Up to 2x leverage with real Fed Funds interest rates
- **Benchmark Comparison** - Compare against any ticker (SPY, QQQ, etc.)
- **Portfolio Analytics** - Sharpe Ratio, CAGR, Alpha/Beta, Max Drawdown
- **Interactive Visualization** - Chart.js powered portfolio growth charts

## 📊 Project Status

- **Test Coverage**: 123 tests (all passing ✅)
- **Code Quality**: Modular architecture with pure functions
- **Documentation**: Complete with PRD, developer guide, and changelog

## 📁 Project Structure

```
finance/
├── app.py                    # Main Flask application & simulation engine
├── requirements.txt          # Python dependencies
├── FEDFUNDS.csv             # Historical Fed Funds rate data
│
├── templates/
│   └── index.html           # Frontend UI
│
├── static/
│   ├── script.js            # Frontend logic & Chart.js
│   └── style.css            # Dark mode styling
│
├── tests/                   # Test suite (123 tests)
│   ├── test_integration_properties.py    # Property-based integration tests
│   ├── test_analytics.py                 # Analytics calculation tests
│   ├── test_calculations.py              # Pure function tests
│   ├── test_margin_trading.py            # Margin & leverage tests
│   ├── test_financial_accuracy.py        # Financial correctness
│   └── ... (13 test files total)
│
├── docs/
│   └── archive/             # Historical development docs
│
├── README.md                # This file
├── CLAUDE.md                # Developer guide for AI assistants
├── PRD.md                   # Product Requirements Document
└── CHANGELOG.md             # Development history
```

## 📖 Documentation

| File | Purpose |
|------|---------|
| **README.md** | Quick start and overview (you are here) |
| **PRD.md** | Product requirements and features specification |
| **CLAUDE.md** | Developer guide for working with this codebase |
| **CHANGELOG.md** | Development history and version changes |
| **docs/archive/** | Historical development documentation |

## 🧪 Testing

```bash
# Run all tests (123 tests)
python -m unittest discover tests/ -v

# Run specific test suite
python -m unittest tests.test_integration_properties -v

# Run analytics tests
python -m unittest tests.test_analytics -v
```

### Test Coverage

- **Integration Tests** - Mathematical properties and consistency
- **Unit Tests** - Pure calculation functions
- **Domain Logic Tests** - Business rules and edge cases
- **Financial Accuracy** - Real-world scenario validation
- **BDD Scenarios** - User story acceptance tests

## 🏗️ Architecture

### Core Simulation Engine

The heart of the application is `calculate_dca_core()` in `app.py`, which processes day-by-day investments:

**Order of Operations** (each trading day):
1. Process dividends (based on overnight share holdings)
2. Charge monthly interest (first day of each month)
3. Execute daily investment (cash first, then margin if enabled)
4. Check margin requirements and force liquidate if needed
5. Record all metrics for charting

### Code Organization

- **Pure Calculation Functions** - Testable, side-effect-free math
- **Data Layer Functions** - Fetch and prepare stock data
- **Domain Logic Functions** - Business rules (dividends, interest, margin calls)
- **Flask Routes** - API endpoints for frontend

## 🛠️ Tech Stack

- **Backend**: Python 3.13, Flask
- **Data Source**: Yahoo Finance API (via yfinance)
- **Data Processing**: pandas
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Visualization**: Chart.js
- **Testing**: unittest (123 tests)

## 💡 For Developers

### First Time Working on This Repo?

1. **Read `CLAUDE.md`** - Comprehensive developer guide with:
   - Setup instructions
   - Architecture overview
   - Testing strategy
   - Common gotchas

2. **Read `PRD.md`** - Understand the product requirements:
   - Feature specifications
   - Financial calculation details
   - Edge case handling

3. **Run the tests**:
   ```bash
   python -m unittest discover tests/ -v
   ```

### Key Concepts

**Cost Basis vs Invested**
- `total_invested`: User's principal contribution only
- `total_cost_basis`: All money spent (Principal + Dividends + Margin)

**Margin Trading**
- Conservative approach: margin used only when cash depletes
- Interest: Fed Funds Rate + 0.5%, charged monthly
- Margin calls: Forced liquidation to restore 25% equity ratio

**Dividend Handling**
- Uses `auto_adjust=False` to prevent double-counting
- Dividends paid on ex-date based on overnight holdings
- Can reinvest (buy more shares) or accumulate as cash

## 📈 Development Philosophy

This codebase follows **property-based testing** principles:

✅ **Test mathematical truths** - `portfolio_value = shares × price + cash`
✅ **Test relationships** - `leverage = portfolio_value / equity`
✅ **Test consistency** - `total_return ≈ ROI` (when no margin)

❌ **Avoid arbitrary thresholds** - No `assert CAGR < 500%` type checks
❌ **Avoid implementation details** - Test behavior, not internals

See `tests/test_integration_properties.py` for examples.

## 🎯 Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for your changes
4. Ensure all tests pass
5. Submit a pull request

**Code Style**: Follow existing patterns in the codebase
**Testing**: All new features require tests
**Documentation**: Update relevant docs for significant changes

## 📝 Recent Updates

See `CHANGELOG.md` for detailed version history.

**Latest (2025-01-25)**:
- Added comprehensive integration tests with property-based validation
- Removed arbitrary threshold checks from analytics
- Reorganized repository structure for better maintainability
- Cleaned up historical development documentation

## 🐛 Found a Bug?

1. Check `docs/archive/` for known historical issues
2. Write a failing test that reproduces the bug
3. Fix the bug
4. Ensure all tests pass
5. Submit a PR

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- Yahoo Finance for historical stock data
- Federal Reserve for Fed Funds rate data
- Chart.js for visualization capabilities

---

**For detailed development history, see `CHANGELOG.md`**
**For AI assistant guidance, see `CLAUDE.md`**

# Changelog

All notable changes to the DCA (Dollar Cost Averaging) Simulator project.

## [Latest] - 2025-01-25

### Added
- **Comprehensive Integration Tests** (`tests/test_integration_properties.py`)
  - Property-based testing for mathematical identities
  - Consistency validation between related metrics
  - Scenario-based validation (flat market, DCA vs lump sum, margin trading)
  - Root cause tests for initial equity calculation

### Fixed
- Removed arbitrary threshold checks in analytics tests
  - Replaced `volatility < 100` check with proper type validation
  - Focus on mathematical properties instead of arbitrary limits

### Changed
- Reorganized repository structure
  - Moved historical development docs to `docs/archive/`
  - Cleaned up root directory for better maintainability

---

## Sprint 3 - Refactoring Completion

### Added
- Modular function architecture with clear separation of concerns
- Pure calculation functions for testability
- Data layer functions for fetching and preparation
- Domain logic functions for business rules

### Improved
- Code readability and maintainability
- Test coverage across all layers
- Documentation for function responsibilities

---

## Sprint 2 - Domain Logic Refactoring

### Added
- Separate functions for core business logic
- Improved margin trading calculations
- Enhanced dividend processing

### Fixed
- Interest calculation timing
- Margin call logic consistency

---

## Sprint 1 - Core Calculation Refactoring

### Added
- Pure calculation functions extracted from main loop
- Comprehensive unit tests for calculations
- Financial accuracy validation

### Fixed
- Cost basis calculation edge cases
- Average cost precision issues

---

## Phase 3 - Polish & Analytics

### Added
- Portfolio analytics (Sharpe Ratio, Calmar Ratio, Alpha/Beta)
- Risk metrics (Volatility, Max Drawdown, Win Rate)
- Performance metrics (CAGR, Total Return %, Best/Worst Days)

### Improved
- UI/UX with analytics visualization
- Benchmark comparison features

---

## Phase 2 - Advanced Features

### Added
- Margin trading support (up to 2x leverage)
- Margin calls and forced liquidation
- Interest rate calculations using Fed Funds data
- Dividend reinvestment options

### Improved
- Account balance tracking
- Cost basis calculation including borrowed funds

---

## Phase 1 - Core DCA Implementation

### Added
- Basic DCA simulator with daily investment tracking
- Historical stock data fetching via Yahoo Finance
- Portfolio value calculation
- Initial investment support
- Benchmark comparison (basic)
- Frontend UI with Chart.js visualization

### Features
- Real historical price data
- Day-by-day simulation
- Dividend tracking
- ROI calculation

---

## Development Notes

For detailed historical development documentation, see `docs/archive/`:
- Sprint completion reports
- Bug analysis and fixing plans
- Refactoring analysis documents
- Phase completion summaries

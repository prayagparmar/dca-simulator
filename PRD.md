# Product Requirements Document: DCA Simulator

## Product Overview

The DCA (Dollar Cost Averaging) Simulator is a web-based financial analysis tool that enables investors to simulate and visualize Dollar Cost Averaging investment strategies with advanced features including dividend reinvestment, margin trading, and benchmark comparisons.

## Target Users

- **Retail Investors**: Individuals planning or evaluating DCA strategies for long-term investing
- **Financial Advisors**: Professionals demonstrating investment strategies to clients
- **Investment Enthusiasts**: Users researching historical performance of DCA strategies
- **Students**: Learning about investment strategies and market behavior

## Core Features

### 1. Basic DCA Simulation

**Description**: Simulate a DCA strategy over any historical time period for stocks, ETFs, and cryptocurrencies.

**User Inputs**:
- **Stock Ticker**: Symbol (with autocomplete suggestions from Yahoo Finance)
- **Start Date**: Beginning of simulation period
- **End Date** (Optional): End of simulation period (defaults to today)
- **Initial Investment**: One-time lump sum investment on day 1
- **Daily Amount**: Amount invested each trading day
- **Account Balance**: Total cash available for the strategy

**Outputs**:
- **Total Invested**: Principal amount contributed by the user
- **Current Value**: Current market value of all shares
- **Total Shares**: Number of shares accumulated
- **ROI (Return on Investment)**: Percentage gain/loss
- **Account Balance**: Remaining cash after all investments

### 2. Dividend Management

**Description**: Track and manage dividend income from the investment.

**Features**:
- **Dividend Tracking**: Automatically fetches dividend history from Yahoo Finance
- **Reinvestment Toggle**: Option to reinvest dividends or accumulate as cash
- **Cumulative Dividends**: Total dividend income received over the period

**Behavior**:
- **Reinvest ON**: Dividends immediately purchase additional shares at current price
- **Reinvest OFF**: Dividends accumulate in cash balance and can fund future daily investments

### 3. Margin Trading (Robinhood-Style)

**Description**: Simulate leveraged investing using margin with realistic constraints and interest charges.

**Parameters**:
- **Margin Ratio**: 1x (no margin), 1.25x, 1.5x, 1.75x, 2x
- **Maintenance Margin**: Minimum equity ratio (default 25%)
- **Interest Rate**: Fed Funds Rate + 0.5%, charged monthly

**Features**:
- **Buying Power**: Automatically borrows when cash is insufficient (up to margin ratio limit)
- **Interest Charges**: Monthly interest on borrowed amount, paid from cash or capitalized to debt
- **Margin Calls**: Triggered when equity ratio drops below maintenance margin
- **Forced Liquidation**: Automatic share sales to restore equity above maintenance level
- **Tracking Metrics**:
  - Total Borrowed
  - Total Interest Paid
  - Current Leverage Ratio
  - Number of Margin Calls
  - Net Portfolio Value (Equity)

### 4. Comparison Features

**Benchmark Comparison**:
- Compare DCA performance against a benchmark ticker (default: SPY)
- Uses same investment parameters for fair comparison
- Displays benchmark value in summary and chart

**No-Margin Comparison** (when using margin):
- Automatically simulates the same strategy without margin
- Shows alternative performance in chart
- Helps visualize the impact of leverage

### 5. Visualization & Analytics

**Interactive Chart** (Chart.js):
- Portfolio Value
- Net Portfolio Value (Equity)
- Total Invested
- Cumulative Dividends
- Account Balance
- Borrowed Amount
- Interest Paid
- Leverage Ratio
- Average Cost per Share
- Benchmark Performance (if enabled)
- No-Margin Performance (if using margin)

**Summary Cards**:
- Total Invested
- Current Value
- Net Portfolio Value
- Total Shares
- Total Dividends
- Benchmark Value
- Account Balance
- ROI
- Total Borrowed
- Interest Paid
- Current Leverage
- Margin Calls
- Average Cost

**Average Cost Calculation**:
- Tracks the average cost per share across all purchases
- Accounts for shares bought with principal, dividends, and margin
- Formula: `Total Cost Basis / Total Shares`
- Distinguishes from "Total Invested" (principal only)

### 6. User Experience Features

**Ticker Autocomplete**:
- Real-time search suggestions from Yahoo Finance
- Displays ticker symbol, company name, asset type, and exchange

**Start Date Warning**:
- Alerts user when requested start date is earlier than available data
- Shows actual start date used in simulation

**Input Formatting**:
- Comma-separated number formatting for readability
- Date pickers for easy selection
- Validation for required fields

**Responsive Design**:
- Dark mode UI with vibrant accent colors
- Mobile-friendly layout
- Clean, modern aesthetic

## Technical Specifications

### Architecture
- **Backend**: Python Flask
- **Data Source**: Yahoo Finance via `yfinance` library
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Visualization**: Chart.js
- **Interest Rate Data**: FRED Economic Data (Fed Funds Rate)

### Key Technical Decisions

**Price Data**:
- Uses `auto_adjust=False` to fetch raw (unadjusted) prices
- Prevents double-counting of dividends when manually reinvesting
- Prices naturally drop on ex-dividend dates, accurately reflecting market behavior

**Investment Accounting**:
- **Total Invested**: Tracks user's principal contribution only
- **Total Cost Basis**: Tracks all money spent on shares (Principal + Dividends + Margin)
- **Average Cost**: Calculated as `Total Cost Basis / Total Shares`
- **Available Principal**: Distinguishes between user capital and recycled dividends

**Margin Trading Logic**:
- Conservative approach: margin used only when cash depletes
- Interest paid from cash first, then capitalized to debt
- Forced liquidation targets restoration to exactly maintenance margin (25%)
- Leverage ratio: `Portfolio Value / Equity`

### Data Flow

1. User submits form with investment parameters
2. Backend fetches historical price and dividend data from Yahoo Finance
3. Simulation runs day-by-day:
   - Process dividends (reinvest or add to cash)
   - Charge monthly interest (if using margin)
   - Execute daily investment (from cash and/or margin)
   - Check for margin call and liquidate if needed
   - Record all metrics
4. Results returned as JSON with summary and time-series data
5. Frontend renders interactive chart and summary cards

## Success Metrics

- **Accuracy**: Simulations produce realistic results comparable to actual market outcomes
- **Performance**: Page loads and calculations complete in under 3 seconds
- **Usability**: Users can complete a simulation with minimal clicks and clear guidance
- **Reliability**: All edge cases handled gracefully (no crashes, helpful error messages)

## Known Limitations

1. **Trading Costs**: Does not account for commissions or transaction fees (assumes zero-fee platform)
2. **Slippage**: Uses closing prices for all trades (no intraday price variation)
3. **Tax Implications**: Does not calculate tax liabilities on dividends or capital gains
4. **Market Hours**: Assumes investment happens on all trading days (no customization for weekly/monthly DCA)
5. **Dividend Timing**: Uses ex-dividend dates for simplicity (not payment dates)

## Future Enhancement Opportunities

- **Tax-Aware Simulations**: Calculate estimated tax liabilities
- **Custom Investment Schedules**: Weekly, bi-weekly, or monthly DCA
- **Transaction Costs**: Configurable commission structure
- **Portfolio Diversification**: Simulate DCA across multiple tickers
- **Export Functionality**: Download results as CSV or PDF
- **Historical Scenarios**: Pre-configured simulations for market events (2008 crash, COVID-19, etc.)
- **Mobile App**: Native iOS/Android applications

## Version History

- **v1.0** (Initial Release): Basic DCA simulation with dividends
- **v2.0** (Margin Trading): Added Robinhood-style margin with realistic constraints
- **v2.1** (Bug Fixes): Fixed dividend double-counting, investment consistency, and average cost calculation
- **v2.2** (Current): Stable release with all core features

---

**Last Updated**: November 23, 2025  
**Document Owner**: Development Team  
**Status**: Active Development

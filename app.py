from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
import requests
import json
import os
from datetime import datetime

app = Flask(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Margin Trading Constants
MARGIN_INTEREST_MARKUP = 0.005  # 0.5% markup added to Fed Funds rate for margin interest
DEFAULT_MAINTENANCE_MARGIN = 0.25  # 25% minimum equity ratio before margin call
NO_MARGIN_RATIO = 1.0  # No margin/leverage used

# Time Constants
MONTHS_PER_YEAR = 12  # Used for annualized interest calculations

# ==============================================================================
# END CONSTANTS
# ==============================================================================

# Load Fed Funds rate data for margin interest calculation
# Use absolute path for production deployment compatibility
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FEDFUNDS_PATH = os.path.join(SCRIPT_DIR, 'FEDFUNDS.csv')
FED_FUNDS_DATA = pd.read_csv(FEDFUNDS_PATH, parse_dates=['observation_date'])
FED_FUNDS_DATA.set_index('observation_date', inplace=True)

def get_fed_funds_rate(date_str):
    """Get Fed Funds rate for a given date. Returns rate as decimal (e.g., 5.33 -> 0.0533)."""
    try:
        date = pd.to_datetime(date_str)
        # Get first day of month for lookup
        month_start = date.replace(day=1)
        
        # Find the most recent rate (equal or before this month)
        available_dates = FED_FUNDS_DATA.index[FED_FUNDS_DATA.index <= month_start]
        if len(available_dates) == 0:
            # No data available, use earliest rate
            rate = FED_FUNDS_DATA.iloc[0]['FEDFUNDS']
        else:
            latest_date = available_dates[-1]
            rate = FED_FUNDS_DATA.loc[latest_date, 'FEDFUNDS']
        
        # Convert percentage to decimal (e.g., 5.33 -> 0.0533)
        return rate / 100.0
    except Exception as e:
        print(f"Error getting Fed Funds rate for {date_str}: {e}")
        return 0.05  # Default to 5% if error


# ==============================================================================
# PURE CALCULATION FUNCTIONS (Sprint 1 Refactoring)
# These functions have no side effects and are easily testable
# ==============================================================================

def calculate_shares_bought(investment_amount, price_per_share):
    """
    Calculate number of shares that can be purchased with given amount.

    Pure function with no side effects.

    Args:
        investment_amount: Dollar amount to invest
        price_per_share: Current price per share

    Returns:
        Number of shares that can be purchased (fractional)

    Example:
        >>> calculate_shares_bought(100, 25)
        4.0
    """
    if price_per_share <= 0:
        return 0
    return investment_amount / price_per_share


def calculate_dividend_income(total_shares, dividend_per_share):
    """
    Calculate total dividend income based on shares held.

    Pure function with no side effects.

    Args:
        total_shares: Number of shares held
        dividend_per_share: Dividend amount per share

    Returns:
        Total dividend income

    Example:
        >>> calculate_dividend_income(100, 0.50)
        50.0
    """
    return total_shares * dividend_per_share


def calculate_monthly_interest(borrowed_amount, fed_funds_rate):
    """
    Calculate monthly interest charge on borrowed amount.

    Uses Fed Funds rate + 0.5% margin, converted to monthly rate.
    Pure function with no side effects.

    Args:
        borrowed_amount: Total amount borrowed on margin
        fed_funds_rate: Annual Fed Funds rate as decimal (e.g., 0.05 for 5%)

    Returns:
        Monthly interest charge

    Example:
        >>> calculate_monthly_interest(10000, 0.05)
        45.83  # (10000 * (0.05 + MARGIN_INTEREST_MARKUP)) / MONTHS_PER_YEAR
    """
    annual_rate = fed_funds_rate + MARGIN_INTEREST_MARKUP  # Add 0.5% markup to Fed Funds rate
    monthly_rate = annual_rate / MONTHS_PER_YEAR
    return borrowed_amount * monthly_rate


def calculate_equity_ratio(portfolio_value, cash_balance, debt):
    """
    Calculate equity ratio for margin requirements.

    Equity ratio = (Portfolio Value + Cash - Debt) / Portfolio Value
    Pure function with no side effects.

    Args:
        portfolio_value: Current value of all shares held
        cash_balance: Available cash (can be None or negative in edge cases)
        debt: Amount borrowed on margin

    Returns:
        Equity ratio as decimal (e.g., 0.25 for 25%)
        Returns 0 if portfolio value is 0 or negative

    Example:
        >>> calculate_equity_ratio(10000, 2000, 5000)
        0.7  # (10000 + 2000 - 5000) / 10000
    """
    if portfolio_value <= 0:
        return 0

    # Use max(0, cash_balance) to handle edge cases
    safe_cash = max(0, cash_balance) if cash_balance is not None else 0
    equity = portfolio_value + safe_cash - debt
    return equity / portfolio_value


def check_insolvency(portfolio_value, cash_balance, debt):
    """
    Detect if account is insolvent (equity ≤ 0).

    An account is insolvent when total equity (assets minus debt) is zero or negative.
    This matches Robinhood's behavior: when your debt exceeds your assets,
    the account is terminated.

    Pure function with no side effects.

    Args:
        portfolio_value: Current value of all shares held
        cash_balance: Available cash (can be None or negative in edge cases)
        debt: Amount borrowed on margin

    Returns:
        bool: True if insolvent (should terminate account), False otherwise

    Example:
        >>> check_insolvency(5000, 1000, 8000)
        True  # Equity = 5000 + 1000 - 8000 = -2000 (INSOLVENT)

        >>> check_insolvency(10000, 2000, 5000)
        False  # Equity = 10000 + 2000 - 5000 = 7000 (solvent)
    """
    # Handle edge cases for cash balance
    safe_cash = max(0, cash_balance) if cash_balance is not None else 0

    # Calculate total equity: assets (portfolio + cash) minus liabilities (debt)
    equity = portfolio_value + safe_cash - debt

    # Account is insolvent if equity is zero or negative
    return equity <= 0


def calculate_target_portfolio_for_margin_call(borrowed_amount, cash_balance, maintenance_margin):
    """
    Calculate target portfolio value after forced liquidation.

    Solves for: equity / portfolio = maintenance_margin
    Where: equity = portfolio + cash - debt
    Result: portfolio = (debt - cash) / (1 - maintenance_margin)

    Pure function with no side effects.

    Args:
        borrowed_amount: Total debt on margin
        cash_balance: Available cash
        maintenance_margin: Required equity ratio (e.g., 0.25 for 25%)

    Returns:
        Target portfolio value to restore margin requirements

    Example:
        >>> calculate_target_portfolio_for_margin_call(10000, 1000, 0.25)
        12000.0  # (10000 - 1000) / (1 - 0.25)
    """
    safe_cash = max(0, cash_balance) if cash_balance is not None else 0
    return (borrowed_amount - safe_cash) / (1 - maintenance_margin)


def calculate_shares_to_sell_for_withdrawal(withdrawal_amount, margin_debt, cash_balance, current_price):
    """
    Calculate shares to sell with margin debt priority.

    Logic:
    1. Repay ALL margin debt first
    2. Then satisfy withdrawal amount
    3. Return shares needed to achieve this

    Args:
        withdrawal_amount: Requested withdrawal amount
        margin_debt: Current margin debt
        cash_balance: Current cash balance
        current_price: Current share price

    Returns:
        shares_to_sell: Number of shares to sell
        debt_repayment: Amount going to debt repayment
        withdrawal: Amount actually withdrawn
    """
    # Total cash needed: repay debt + withdrawal amount
    total_needed = margin_debt + withdrawal_amount

    # Cash already available (handle None for infinite cash mode)
    available_cash = max(0, cash_balance if cash_balance is not None else 0)

    # Additional cash needed from selling shares
    cash_from_sales_needed = max(0, total_needed - available_cash)

    # Shares to sell
    shares_to_sell = cash_from_sales_needed / current_price if current_price > 0 else 0

    # Calculate actual amounts
    sale_proceeds = shares_to_sell * current_price
    total_cash = available_cash + sale_proceeds

    # Priority 1: Repay debt
    debt_repayment = min(total_cash, margin_debt)

    # Priority 2: Withdraw
    remaining_cash = total_cash - debt_repayment
    actual_withdrawal = min(remaining_cash, withdrawal_amount)

    return shares_to_sell, debt_repayment, actual_withdrawal


# ==============================================================================
# END PURE CALCULATION FUNCTIONS
# ==============================================================================


# ==============================================================================
# ANALYTICS CALCULATION FUNCTIONS (Portfolio Analytics Feature)
# These functions calculate risk and performance metrics from time series data
# ==============================================================================

def calculate_total_return_percent(initial_value, final_value):
    """
    Calculate total return as a percentage.

    Pure function with no side effects.

    Args:
        initial_value: Starting portfolio value
        final_value: Ending portfolio value

    Returns:
        Total return as percentage (e.g., 45.2 for 45.2% gain)
        Returns 0 if initial_value is 0 or negative

    Example:
        >>> calculate_total_return_percent(10000, 14520)
        45.2
    """
    if initial_value <= 0:
        return 0
    return ((final_value - initial_value) / initial_value) * 100


def calculate_cagr(initial_value, final_value, num_days):
    """
    Calculate Compound Annual Growth Rate (CAGR).

    CAGR = (Final Value / Initial Value)^(365/days) - 1
    Pure function with no side effects.

    Args:
        initial_value: Starting portfolio value
        final_value: Ending portfolio value
        num_days: Number of days in the period

    Returns:
        CAGR as percentage (e.g., 24.5 for 24.5% annual growth)
        Returns 0 if initial_value is 0 or num_days is 0

    Example:
        >>> calculate_cagr(10000, 14520, 365)
        45.2
    """
    if initial_value <= 0 or num_days <= 0:
        return 0
    years = num_days / 365.0
    if years == 0:
        return 0
    return (pow(final_value / initial_value, 1 / years) - 1) * 100


def calculate_daily_returns(portfolio_values):
    """
    Calculate daily returns from portfolio values.

    Daily Return = (Value[i] - Value[i-1]) / Value[i-1]
    Pure function with no side effects.

    Args:
        portfolio_values: List of daily portfolio values

    Returns:
        List of daily returns as decimals (e.g., 0.05 for 5% gain)
        First day return is 0 (no prior day to compare)

    Example:
        >>> calculate_daily_returns([100, 105, 103])
        [0, 0.05, -0.019047619047619]
    """
    if len(portfolio_values) < 2:
        return [0]

    returns = [0]  # First day has no prior day
    for i in range(1, len(portfolio_values)):
        if portfolio_values[i-1] > 0:
            daily_return = (portfolio_values[i] - portfolio_values[i-1]) / portfolio_values[i-1]
            returns.append(daily_return)
        else:
            returns.append(0)
    return returns


def calculate_volatility(daily_returns):
    """
    Calculate annualized volatility (standard deviation of returns).

    Volatility = Std Dev of Daily Returns * sqrt(252 trading days)
    Pure function with no side effects.

    Args:
        daily_returns: List of daily returns as decimals

    Returns:
        Annualized volatility as percentage (e.g., 18.2 for 18.2% volatility)
        Returns 0 if insufficient data

    Example:
        >>> calculate_volatility([0, 0.01, -0.01, 0.02, -0.005])
        # Returns annualized std dev
    """
    if len(daily_returns) < 2:
        return 0

    # Calculate mean
    mean_return = sum(daily_returns) / len(daily_returns)

    # Calculate variance
    variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)

    # Calculate standard deviation
    std_dev = variance ** 0.5

    # Annualize (252 trading days per year)
    annualized_volatility = std_dev * (252 ** 0.5)

    return annualized_volatility * 100  # Convert to percentage


def calculate_sharpe_ratio(daily_returns, risk_free_rate=0.02):
    """
    Calculate Sharpe Ratio (risk-adjusted return).

    Sharpe = (Mean Return - Risk Free Rate) / Std Dev * sqrt(252)
    Pure function with no side effects.

    Args:
        daily_returns: List of daily returns as decimals
        risk_free_rate: Annual risk-free rate as decimal (default 2%)

    Returns:
        Sharpe ratio as decimal (e.g., 1.85)
        Returns 0 if insufficient data or zero volatility

    Interpretation:
        < 1.0: Poor risk-adjusted return
        1.0-2.0: Good
        2.0-3.0: Very good
        > 3.0: Excellent

    Example:
        >>> calculate_sharpe_ratio([0, 0.01, -0.01, 0.02])
        # Returns risk-adjusted return metric
    """
    if len(daily_returns) < 2:
        return 0

    # Calculate mean daily return
    mean_return = sum(daily_returns) / len(daily_returns)

    # Calculate standard deviation
    variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
    std_dev = variance ** 0.5

    if std_dev == 0:
        return 0

    # Convert annual risk-free rate to daily
    daily_risk_free = risk_free_rate / 252

    # Calculate Sharpe ratio and annualize
    sharpe = ((mean_return - daily_risk_free) / std_dev) * (252 ** 0.5)

    return sharpe


def calculate_max_drawdown(portfolio_values):
    """
    Calculate maximum drawdown (worst peak-to-trough decline).

    Max Drawdown = Max((Peak - Trough) / Peak)
    Pure function with no side effects.

    Args:
        portfolio_values: List of daily portfolio values

    Returns:
        Tuple of (max_drawdown_percent, peak_date_idx, trough_date_idx)
        max_drawdown_percent is negative (e.g., -12.4 for 12.4% decline)
        Returns (0, 0, 0) if no drawdown

    Example:
        >>> calculate_max_drawdown([100, 110, 105, 95, 105])
        (-13.636363636363635, 1, 3)  # 13.6% drop from day 1 to day 3
    """
    if len(portfolio_values) < 2:
        return 0, 0, 0

    max_drawdown = 0
    peak_value = portfolio_values[0]
    peak_idx = 0
    trough_idx = 0
    max_dd_peak_idx = 0
    max_dd_trough_idx = 0

    for i, value in enumerate(portfolio_values):
        if value > peak_value:
            peak_value = value
            peak_idx = i

        if peak_value > 0:
            drawdown = (value - peak_value) / peak_value
            if drawdown < max_drawdown:
                max_drawdown = drawdown
                max_dd_peak_idx = peak_idx
                max_dd_trough_idx = i

    return max_drawdown * 100, max_dd_peak_idx, max_dd_trough_idx  # Convert to percentage


def calculate_win_rate(daily_returns):
    """
    Calculate win rate (percentage of days with positive returns).

    Win Rate = (Days with positive returns / Total days) * 100
    Pure function with no side effects.

    Args:
        daily_returns: List of daily returns as decimals

    Returns:
        Win rate as percentage (e.g., 58.3 for 58.3% of days positive)
        Returns 0 if no data

    Example:
        >>> calculate_win_rate([0, 0.01, -0.01, 0.02, 0.01, -0.005])
        60.0  # 3 out of 5 non-zero days were positive
    """
    if len(daily_returns) <= 1:
        return 0

    # Skip first day (always 0)
    returns_without_first = daily_returns[1:]

    if len(returns_without_first) == 0:
        return 0

    winning_days = sum(1 for r in returns_without_first if r > 0)
    total_days = len(returns_without_first)

    return (winning_days / total_days) * 100


def calculate_best_worst_days(daily_returns, dates):
    """
    Calculate best and worst single-day returns.

    Pure function with no side effects.

    Args:
        daily_returns: List of daily returns as decimals
        dates: List of date strings matching returns

    Returns:
        Tuple of (best_return_pct, best_date, worst_return_pct, worst_date)
        Returns as percentages (e.g., 8.2 for 8.2% gain)

    Example:
        >>> calculate_best_worst_days([0, 0.05, -0.03, 0.02], ['2024-01-01', '2024-01-02', ...])
        (5.0, '2024-01-02', -3.0, '2024-01-03')
    """
    if len(daily_returns) <= 1:
        return 0, None, 0, None

    # Skip first day (always 0)
    returns_without_first = daily_returns[1:]
    dates_without_first = dates[1:] if len(dates) > 1 else []

    if len(returns_without_first) == 0:
        return 0, None, 0, None

    best_return = max(returns_without_first)
    worst_return = min(returns_without_first)

    best_idx = returns_without_first.index(best_return)
    worst_idx = returns_without_first.index(worst_return)

    best_date = dates_without_first[best_idx] if best_idx < len(dates_without_first) else None
    worst_date = dates_without_first[worst_idx] if worst_idx < len(dates_without_first) else None

    return best_return * 100, best_date, worst_return * 100, worst_date


def calculate_calmar_ratio(cagr, max_drawdown):
    """
    Calculate Calmar Ratio (CAGR / |Max Drawdown|).

    Measures return per unit of downside risk.
    Pure function with no side effects.

    Args:
        cagr: Compound annual growth rate as percentage
        max_drawdown: Maximum drawdown as negative percentage

    Returns:
        Calmar ratio as decimal (e.g., 1.97)
        Returns 0 if max_drawdown is 0

    Interpretation:
        < 1.0: Poor return for risk taken
        1.0-3.0: Good
        3.0-5.0: Very good
        > 5.0: Excellent

    Example:
        >>> calculate_calmar_ratio(24.5, -12.4)
        1.975806451612903
    """
    if max_drawdown >= 0:  # No drawdown or invalid
        return 0

    return cagr / abs(max_drawdown)


def calculate_alpha_beta(portfolio_returns, benchmark_returns):
    """
    Calculate Alpha and Beta vs benchmark.

    Beta = Covariance(Portfolio, Benchmark) / Variance(Benchmark)
    Alpha = Annualized(Mean Portfolio Return - Beta * Mean Benchmark Return)

    Pure function with no side effects.

    Args:
        portfolio_returns: List of daily returns for portfolio
        benchmark_returns: List of daily returns for benchmark

    Returns:
        Tuple of (alpha_pct, beta)
        alpha_pct: Annualized alpha as percentage (e.g., 11.2 for 11.2% outperformance)
        beta: Beta coefficient (e.g., 1.15 for 15% more volatile than benchmark)
        Returns (0, 1.0) if insufficient data

    Example:
        >>> calculate_alpha_beta([0, 0.02, -0.01], [0, 0.015, -0.005])
        # Returns (alpha%, beta)
    """
    if len(portfolio_returns) < 2 or len(benchmark_returns) < 2:
        return 0, 1.0

    if len(portfolio_returns) != len(benchmark_returns):
        return 0, 1.0

    # Skip first day (always 0 for both)
    port_returns = portfolio_returns[1:]
    bench_returns = benchmark_returns[1:]

    if len(port_returns) == 0:
        return 0, 1.0

    # Calculate means
    port_mean = sum(port_returns) / len(port_returns)
    bench_mean = sum(bench_returns) / len(bench_returns)

    # Calculate covariance and variance
    covariance = sum((port_returns[i] - port_mean) * (bench_returns[i] - bench_mean)
                     for i in range(len(port_returns))) / len(port_returns)

    variance = sum((r - bench_mean) ** 2 for r in bench_returns) / len(bench_returns)

    if variance == 0:
        return 0, 1.0

    # Calculate beta
    beta = covariance / variance

    # Calculate alpha (annualized)
    daily_alpha = port_mean - (beta * bench_mean)
    annualized_alpha = daily_alpha * 252 * 100  # Convert to percentage

    return annualized_alpha, beta


def calculate_sharpe_ratio_from_cagr(cagr, volatility, risk_free_rate=0.02):
    """
    Calculate Sharpe Ratio from CAGR for DCA strategies.

    This function is designed for DCA portfolios where daily returns are
    contaminated by contributions. Uses CAGR instead of mean daily returns.

    Formula: Sharpe = (CAGR - Risk-Free Rate) / Volatility

    Args:
        cagr: Annualized return as decimal (e.g., 0.15 for 15%)
        volatility: Annualized volatility as percentage (e.g., 25.5 for 25.5%)
        risk_free_rate: Annual risk-free rate as decimal (default 2%)

    Returns:
        Sharpe ratio as decimal
    """
    if volatility == 0:
        return 0

    # CAGR and risk-free are decimals, volatility is percentage
    sharpe = (cagr - risk_free_rate) / (volatility / 100)
    return sharpe


def calculate_alpha_from_cagr(portfolio_cagr, benchmark_cagr, beta):
    """
    Calculate Alpha from CAGR for DCA strategies.

    This function is designed for DCA portfolios where daily returns are
    contaminated by contributions. Uses CAGR instead of daily returns.

    Formula: Alpha = Portfolio CAGR - (Beta × Benchmark CAGR)

    Args:
        portfolio_cagr: Portfolio annualized return as decimal (e.g., 0.15 for 15%)
        benchmark_cagr: Benchmark annualized return as decimal (e.g., 0.10 for 10%)
        beta: Beta coefficient (correlation with benchmark)

    Returns:
        Alpha as percentage (e.g., 5.2 for 5.2%)
    """
    alpha = (portfolio_cagr - (beta * benchmark_cagr)) * 100
    return alpha


# ==============================================================================
# END ANALYTICS CALCULATION FUNCTIONS
# ==============================================================================


# ==============================================================================
# DATA LAYER FUNCTIONS (Sprint 3 Refactoring)
# These functions handle data fetching and preparation
# ==============================================================================


def fetch_stock_data(ticker, start_date, end_date):
    """
    Fetch historical stock price data from Yahoo Finance.

    Validates data quality and ensures consistent date format.
    Includes retry logic for production reliability.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'SPY')
        start_date: Start date for historical data
        end_date: End date for historical data

    Returns:
        pandas DataFrame with historical price data (index as string dates)
        Returns None if data is unavailable or invalid

    Example:
        >>> hist = fetch_stock_data('AAPL', '2024-01-01', '2024-12-31')
        >>> hist.index[0]  # Returns string date
        '2024-01-02'
    """
    import time
    max_retries = 3
    retry_delay = 1  # seconds

    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(ticker)
            # Get data with auto_adjust=False to get raw prices
            # This prevents double-counting dividends when we manually reinvest them
            # yfinance 0.2.66+ uses curl_cffi which handles headers automatically
            hist = stock.history(start=start_date, end=end_date, auto_adjust=False)

            if hist.empty:
                print(f"WARNING: {ticker} returned empty data for {start_date} to {end_date} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                return None

            # Validate price data - handle NaN/None values
            if hist['Close'].isnull().any():
                print(f"WARNING: {ticker} has missing price data in range {start_date} to {end_date}")
                return None

            # Ensure index is string format for consistency
            if isinstance(hist.index, pd.DatetimeIndex):
                hist.index = hist.index.strftime('%Y-%m-%d')

            print(f"SUCCESS: Fetched {len(hist)} days of data for {ticker}")
            return hist

        except Exception as e:
            print(f"ERROR fetching stock data for {ticker} (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            return None

    return None


def prepare_dividends(stock, start_date, end_date):
    """
    Prepare dividend data for simulation.

    Fetches, filters, and formats dividend data with consistent date indexing.

    Args:
        stock: yfinance Ticker object
        start_date: Start date for filtering dividends
        end_date: End date for filtering dividends

    Returns:
        pandas Series with dividend amounts indexed by date (string format)
        Returns empty Series if no dividends or error occurs

    Example:
        >>> stock = yf.Ticker('AAPL')
        >>> divs = prepare_dividends(stock, '2024-01-01', '2024-12-31')
        >>> divs.get('2024-05-10')  # Returns dividend amount or None
        0.25
    """
    try:
        # Get dividends from stock object
        dividends = stock.dividends

        # Ensure dividend index is DatetimeIndex before filtering
        if not isinstance(dividends.index, pd.DatetimeIndex):
            try:
                dividends.index = pd.to_datetime(dividends.index)
            except:
                # If conversion fails, create empty dividend series
                print(f"WARNING: Could not convert dividend dates, assuming no dividends")
                return pd.Series(dtype=float)

        # Filter dividends within range
        if start_date and end_date and not dividends.empty:
            try:
                dividends = dividends[start_date:end_date]
            except Exception as e:
                print(f"WARNING: Could not filter dividends: {e}")
                return pd.Series(dtype=float)

        # Convert to string format for consistent lookup
        if isinstance(dividends.index, pd.DatetimeIndex):
            dividends.index = dividends.index.strftime('%Y-%m-%d')

        return dividends

    except Exception as e:
        print(f"ERROR preparing dividends: {e}")
        return pd.Series(dtype=float)


def align_to_target_dates(hist, target_dates):
    """
    Align historical data to target dates using forward/backward fill.

    Used to synchronize benchmark data with main ticker's trading days.

    Args:
        hist: pandas DataFrame with historical data
        target_dates: List of target date strings to align to

    Returns:
        pandas DataFrame aligned to target dates
        Returns None if alignment results in all NaN values

    Example:
        >>> main_dates = ['2024-01-02', '2024-01-03', '2024-01-04']
        >>> benchmark_hist = fetch_stock_data('SPY', '2024-01-01', '2024-01-10')
        >>> aligned = align_to_target_dates(benchmark_hist, main_dates)
        >>> len(aligned) == len(main_dates)
        True

    Notes:
        - Forward fills to handle weekends/holidays (use last known price)
        - Backfills for any initial missing data (e.g., if start date is holiday)
        - Returns None if data cannot be aligned (all NaNs)
    """
    try:
        # Reindex to match target dates exactly
        hist = hist.reindex(target_dates)

        # Forward fill to handle weekends/holidays (use last known price)
        hist = hist.ffill()

        # Backfill for any initial missing data (e.g. if start date is a holiday)
        hist = hist.bfill()

        # If still has NaNs (e.g. no data at all), return None
        if hist.isnull().all().all():
            return None

        return hist

    except Exception as e:
        print(f"ERROR aligning to target dates: {e}")
        return None


def find_common_date_range(ticker1, ticker2, start_date, end_date):
    """
    Find the common date range between two tickers.

    When comparing a portfolio against a benchmark, we should only use dates
    where BOTH tickers have actual data. This prevents creating synthetic
    data through back-filling.

    Args:
        ticker1: First ticker symbol
        ticker2: Second ticker symbol
        start_date: Requested start date
        end_date: Requested end date

    Returns:
        tuple: (common_start_date, common_end_date, ticker1_data, ticker2_data)
        Returns (None, None, None, None) if no common range exists

    Example:
        >>> common_start, common_end, data1, data2 = find_common_date_range('NEWCO', 'SPY', '2020-01-01', '2024-12-31')
        >>> # If NEWCO only has data from 2024-01-01, common_start will be '2024-01-01'
    """
    # Fetch data for both tickers
    ticker1_data = fetch_stock_data(ticker1, start_date, end_date)
    ticker2_data = fetch_stock_data(ticker2, start_date, end_date)

    # If either ticker has no data, return None
    if ticker1_data is None or ticker2_data is None:
        return None, None, None, None

    # Get actual date ranges from the data
    ticker1_dates = set(ticker1_data.index.tolist())
    ticker2_dates = set(ticker2_data.index.tolist())

    # Find common dates (intersection)
    common_dates = ticker1_dates & ticker2_dates

    if not common_dates:
        return None, None, None, None

    # Sort to find earliest and latest common dates
    common_dates_sorted = sorted(common_dates)
    common_start = common_dates_sorted[0]
    common_end = common_dates_sorted[-1]

    return common_start, common_end, ticker1_data, ticker2_data


# ==============================================================================
# END DATA LAYER FUNCTIONS
# ==============================================================================


# ==============================================================================
# DOMAIN LOGIC FUNCTIONS (Sprint 2 Refactoring)
# These functions encapsulate business rules and have side effects
# ==============================================================================

def process_dividend(total_shares, dividend_per_share, price, reinvest, current_balance, total_cost_basis):
    """
    Process dividend payment - either reinvest or add to cash balance.

    Domain logic function with business rules.

    Args:
        total_shares: Current shares held (to calculate dividend income)
        dividend_per_share: Dividend amount per share
        price: Current share price (for reinvestment)
        reinvest: Whether to reinvest dividends
        current_balance: Current cash balance (can be None for infinite cash)
        total_cost_basis: Current cost basis

    Returns:
        Tuple of (shares_added, new_cost_basis, new_balance, dividend_income)

    Example:
        >>> process_dividend(100, 0.50, 25, True, 1000, 5000)
        (2.0, 5050.0, 1000, 50.0)  # Reinvested $50 into 2 shares
    """
    dividend_income = calculate_dividend_income(total_shares, dividend_per_share)

    if reinvest:
        # Reinvest: Buy shares with dividend
        shares_added = calculate_shares_bought(dividend_income, price)
        new_cost_basis = total_cost_basis + dividend_income
        new_balance = current_balance  # Balance unchanged when reinvesting
        return shares_added, new_cost_basis, new_balance, dividend_income
    else:
        # Don't reinvest: Add to cash balance
        shares_added = 0
        new_cost_basis = total_cost_basis  # Cost basis unchanged
        if current_balance is not None:
            new_balance = current_balance + dividend_income
        else:
            new_balance = None  # Infinite cash mode
        return shares_added, new_cost_basis, new_balance, dividend_income


def process_interest_charge(borrowed_amount, fed_rate, current_balance):
    """
    Process monthly interest charge - pay from cash or capitalize to debt.

    Domain logic function implementing interest payment rules.

    Args:
        borrowed_amount: Current margin debt
        fed_rate: Annual Fed Funds rate as decimal
        current_balance: Current cash balance (can be None)

    Returns:
        Tuple of (new_balance, new_borrowed_amount, interest_paid)

    Example:
        >>> process_interest_charge(10000, 0.05, 1000)
        (954.17, 10000, 45.83)  # Paid $45.83 from cash

        >>> process_interest_charge(10000, 0.05, 20)
        (0, 10025.83, 45.83)  # Only $20 cash, rest capitalized
    """
    interest_charge = calculate_monthly_interest(borrowed_amount, fed_rate)

    if current_balance is None:
        # Infinite cash mode - shouldn't happen with margin, but handle it
        return None, borrowed_amount, interest_charge

    if current_balance >= interest_charge:
        # Have enough cash to pay interest
        new_balance = current_balance - interest_charge
        new_balance = max(0, new_balance)  # Safety: prevent negative
        return new_balance, borrowed_amount, interest_charge
    else:
        # Not enough cash - capitalize interest into margin debt
        paid_from_cash = max(0, current_balance)
        unpaid_interest = interest_charge - paid_from_cash
        new_borrowed_amount = borrowed_amount + unpaid_interest
        return 0, new_borrowed_amount, interest_charge


def execute_purchase(daily_investment, price, current_balance, borrowed_amount,
                    margin_ratio, total_shares, available_principal):
    """
    Execute daily purchase with margin-aware logic.

    Implements Robinhood-style margin: use cash first, borrow only when needed.

    Args:
        daily_investment: Amount to invest today
        price: Current share price
        current_balance: Available cash
        borrowed_amount: Current margin debt
        margin_ratio: Maximum leverage ratio (e.g., 2.0 for 2x)
        total_shares: Current shares held
        available_principal: Remaining user principal (not dividends/margin)

    Returns:
        Tuple of (shares_bought, cash_used, margin_borrowed, actual_investment,
                 principal_used, new_balance, new_borrowed_amount)
    """
    shares_bought = 0
    cash_used = 0
    margin_borrowed = 0
    actual_investment = 0
    principal_used = 0

    if current_balance is None:
        # Infinite cash mode
        actual_investment = daily_investment
        shares_bought = calculate_shares_bought(actual_investment, price)
        cash_used = daily_investment
        principal_used = daily_investment
        return shares_bought, cash_used, 0, actual_investment, principal_used, None, borrowed_amount

    if margin_ratio > 1.0:
        # Margin enabled - can borrow if needed
        if current_balance >= daily_investment:
            # Have enough cash - use it, don't borrow
            actual_investment = daily_investment
            cash_used = daily_investment
            margin_borrowed = 0
        else:
            # Calculate max investment capacity based on margin ratio
            current_portfolio_value = total_shares * price
            current_equity = current_portfolio_value + max(0, current_balance) - borrowed_amount

            # Max portfolio value allowed = equity * margin_ratio
            max_portfolio_value = current_equity * margin_ratio

            # Max we can add to portfolio (Buying Power remaining)
            max_investment_capacity = max(0, max_portfolio_value - current_portfolio_value)

            if daily_investment <= max_investment_capacity:
                # Can invest full amount
                actual_investment = daily_investment
                cash_used = max(0, current_balance)
                margin_borrowed = daily_investment - cash_used
            else:
                # Hit margin limit - cap investment at max capacity
                actual_investment = max_investment_capacity
                cash_used = min(actual_investment, max(0, current_balance))
                margin_borrowed = actual_investment - cash_used
    else:
        # No margin - can only invest available cash
        if current_balance >= daily_investment:
            actual_investment = daily_investment
            cash_used = daily_investment
        else:
            # Not enough cash and no margin - invest what we have
            actual_investment = max(0, current_balance)
            cash_used = max(0, current_balance)

    # Calculate shares bought
    if actual_investment > 0:
        shares_bought = calculate_shares_bought(actual_investment, price)

    # Track principal used
    if cash_used > 0:
        principal_used = min(cash_used, available_principal)

    # Calculate new balances
    new_balance = current_balance - cash_used if current_balance is not None else None
    new_balance = max(0, new_balance) if new_balance is not None else None
    new_borrowed_amount = borrowed_amount + margin_borrowed

    return shares_bought, cash_used, margin_borrowed, actual_investment, principal_used, new_balance, new_borrowed_amount


def execute_margin_call(total_shares, price, borrowed_amount, current_balance, maintenance_margin):
    """
    Execute forced liquidation to restore margin requirements.

    Implements margin call logic: sell shares to restore equity to maintenance margin.

    Args:
        total_shares: Current shares held
        price: Current share price
        borrowed_amount: Current margin debt
        current_balance: Current cash balance
        maintenance_margin: Required equity ratio (e.g., 0.25 for 25%)

    Returns:
        Tuple of (shares_remaining, new_balance, new_borrowed_amount, margin_call_triggered)

    Example:
        >>> execute_margin_call(200, 60, 10000, 0, 0.25)
        # Portfolio $12k, debt $10k, equity $2k = 16.7% < 25%
        # Must sell to restore to 25%
    """
    current_portfolio_value = total_shares * price
    equity_ratio = calculate_equity_ratio(current_portfolio_value, current_balance, borrowed_amount)

    # Check if margin call is needed
    if equity_ratio >= maintenance_margin:
        # No margin call needed
        return total_shares, current_balance, borrowed_amount, False

    # Margin call triggered!
    target_portfolio_value = calculate_target_portfolio_for_margin_call(
        borrowed_amount, current_balance, maintenance_margin
    )

    if target_portfolio_value > 0 and target_portfolio_value < current_portfolio_value:
        # Sell shares to reduce portfolio to target value
        value_to_sell = current_portfolio_value - target_portfolio_value
        shares_to_sell = calculate_shares_bought(value_to_sell, price)
        shares_to_sell = min(shares_to_sell, total_shares)  # Can't sell more than we have

        # Execute forced sale
        sale_proceeds = shares_to_sell * price
        new_shares = total_shares - shares_to_sell

        # Handle None balance safely
        if current_balance is None:
            new_balance = None
            new_borrowed_amount = borrowed_amount  # Can't pay debt without balance tracking
        else:
            new_balance = current_balance + sale_proceeds

            # Use proceeds to pay down margin debt
            debt_repayment = min(sale_proceeds, borrowed_amount)
            new_borrowed_amount = borrowed_amount - debt_repayment
            new_balance = new_balance - debt_repayment
            new_balance = max(0, new_balance)  # Safety: prevent negative

        return new_shares, new_balance, new_borrowed_amount, True
    else:
        # Can't recover - liquidate everything
        sale_proceeds = total_shares * price
        new_shares = 0

        # Handle None balance safely
        if current_balance is None:
            new_balance = None
            new_borrowed_amount = borrowed_amount  # Can't pay debt without balance tracking
        else:
            new_balance = current_balance + sale_proceeds

            # Pay off as much debt as possible
            debt_repayment = min(new_balance, borrowed_amount)
            new_borrowed_amount = borrowed_amount - debt_repayment
            new_balance = new_balance - debt_repayment
            new_balance = max(0, new_balance)  # Safety: prevent negative

        return new_shares, new_balance, new_borrowed_amount, True


def execute_monthly_withdrawal(withdrawal_amount, total_shares, price, borrowed_amount, current_balance, total_cost_basis):
    """
    Execute monthly withdrawal with margin-aware logic.

    Priority:
    1. Repay ALL margin debt
    2. Withdraw requested amount
    3. Keep remainder in cash

    Args:
        withdrawal_amount: Requested monthly withdrawal
        total_shares: Current shares owned
        price: Current share price
        borrowed_amount: Current margin debt
        current_balance: Current cash balance
        total_cost_basis: Current total cost basis

    Returns:
        new_shares: Shares remaining after sale
        new_balance: Cash balance after withdrawal
        new_borrowed_amount: Debt remaining
        new_cost_basis: Updated cost basis
        shares_sold: Number of shares sold
        debt_repaid: Amount of debt repaid
        amount_withdrawn: Actual amount withdrawn
    """
    # Calculate shares to sell
    shares_to_sell, debt_repayment, actual_withdrawal = calculate_shares_to_sell_for_withdrawal(
        withdrawal_amount, borrowed_amount, current_balance, price
    )

    # Execute sale
    shares_sold = min(shares_to_sell, total_shares)  # Can't sell more than owned
    sale_proceeds = shares_sold * price

    # Update cost basis proportionally
    if total_shares > 0:
        cost_basis_reduction = total_cost_basis * (shares_sold / total_shares)
        new_cost_basis = total_cost_basis - cost_basis_reduction
    else:
        new_cost_basis = total_cost_basis

    # Update shares
    new_shares = total_shares - shares_sold

    # Update cash: add sale proceeds (handle None for infinite cash mode)
    safe_balance = current_balance if current_balance is not None else 0
    new_balance = safe_balance + sale_proceeds

    # Priority 1: Repay debt
    actual_debt_repayment = min(new_balance, borrowed_amount)
    new_borrowed_amount = borrowed_amount - actual_debt_repayment
    new_balance = new_balance - actual_debt_repayment

    # Priority 2: Withdraw
    actual_withdrawal = min(new_balance, withdrawal_amount)
    new_balance = new_balance - actual_withdrawal

    # Return None for balance if in infinite cash mode
    if current_balance is None:
        new_balance = None

    return new_shares, new_balance, new_borrowed_amount, new_cost_basis, shares_sold, actual_debt_repayment, actual_withdrawal


# ==============================================================================
# END DOMAIN LOGIC FUNCTIONS
# ==============================================================================


def should_invest_today(date_str, start_date_str, frequency, last_investment_month):
    """
    Determine if investment should occur today based on frequency setting.

    Args:
        date_str: Current date as string 'YYYY-MM-DD'
        start_date_str: Start date as string 'YYYY-MM-DD'
        frequency: 'DAILY', 'WEEKLY', or 'MONTHLY'
        last_investment_month: Last month invested (format 'YYYY-MM') or None

    Returns:
        tuple: (should_invest: bool, updated_last_month: str or None)
    """
    if frequency == 'DAILY':
        return True, last_investment_month

    try:
        current_date = pd.to_datetime(date_str)
    except (ValueError, pd.errors.OutOfBoundsDatetime):
        # Fallback to daily for invalid dates
        return True, last_investment_month

    if frequency == 'WEEKLY':
        try:
            start_date = pd.to_datetime(start_date_str)
            should_invest = current_date.dayofweek == start_date.dayofweek
            return should_invest, last_investment_month
        except (ValueError, pd.errors.OutOfBoundsDatetime):
            # Fallback to daily for invalid dates
            return True, last_investment_month

    if frequency == 'MONTHLY':
        current_month = current_date.strftime('%Y-%m')
        if current_month != last_investment_month:
            return True, current_month
        return False, last_investment_month

    # Default to daily for unknown frequencies
    return True, last_investment_month


@app.route('/')
def index():
    return render_template('index.html')


def calculate_dca_core(ticker, start_date, end_date, amount, initial_amount, reinvest, target_dates=None, account_balance=None, margin_ratio=NO_MARGIN_RATIO, maintenance_margin=DEFAULT_MAINTENANCE_MARGIN, withdrawal_threshold=None, monthly_withdrawal_amount=None, frequency='DAILY'):
    # Fetch historical price data
    hist = fetch_stock_data(ticker, start_date, end_date)
    if hist is None:
        return None

    # Prepare dividend data
    stock = yf.Ticker(ticker)  # Need stock object for dividends
    dividends = prepare_dividends(stock, start_date, end_date)

    # Align to target dates if provided (for benchmark synchronization)
    if target_dates:
        hist = align_to_target_dates(hist, target_dates)
        if hist is None:
            return None

    # Initialize simulation variables
    total_invested = 0  # Tracks user's actual capital invested (excludes dividends and margin)
    total_cost_basis = 0  # Tracks total money spent on shares (Principal + Dividends + Margin)

    # available_principal: Tracks remaining user capital (not dividends or margin)
    # Purpose: Distinguish between "user's money" and "recycled dividends" for total_invested metric
    # - Starts at account_balance (initial capital)
    # - Decreases when cash is used to buy shares
    # - Does NOT increase when dividends are received (those aren't new capital)
    # - Used to calculate total_invested = sum of principal actually deployed
    # Example: $10k initial, buy $100/day = available_principal decreases by $100 daily
    available_principal = account_balance if account_balance is not None else 0

    total_shares = 0
    cumulative_dividends = 0

    # current_balance: The actual liquid cash in account
    # - Decreases when buying shares
    # - Increases when dividends received (if not reinvested)
    # - Used for margin calculations and purchase decisions
    # - Single source of truth for available funds
    current_balance = account_balance

    # Margin trading variables
    borrowed_amount = 0.0
    total_interest_paid = 0.0
    margin_calls_triggered = 0
    margin_call_dates = []  # Track dates when margin calls occur
    margin_call_details = []  # Track detailed information for each margin call
    last_interest_month = None  # Track when we last charged interest

    # Withdrawal tracking variables
    withdrawal_mode_active = False
    withdrawal_mode_start_date = None
    total_withdrawn = 0.0
    withdrawal_dates = []
    withdrawal_details = []
    last_withdrawal_month = None

    # Investment frequency tracking
    last_investment_month = None  # Track monthly investments

    # Insolvency tracking variables (matches Robinhood behavior)
    insolvency_detected = False
    insolvency_date = None
    min_equity = float('inf')  # Track actual minimum equity (can go negative)
    min_equity_date = None
    peak_equity = 0  # Track peak for actual drawdown calculation

    dates = []
    invested_values = []
    portfolio_values = []
    dividend_values = []
    balance_values = []
    borrowed_values = []
    interest_values = []
    net_portfolio_values = []
    leverage_values = []  # Track leverage ratio over time
    average_cost_values = [] # Track average cost per share
    withdrawal_mode_values = []  # Track withdrawal mode status (boolean)
    withdrawal_amount_values = []  # Track cumulative withdrawn amount

    first_day = True

    for date, row in hist.iterrows():
        """
        DAILY ORDER OF OPERATIONS (executed each trading day):
        1. Check margin requirements - FIRST! Force liquidation if equity < maintenance margin
        2. Check insolvency - STOP simulation if equity ≤ $0 (matches Robinhood behavior)
        3. Check withdrawal threshold - activate withdrawal mode if net value >= threshold
           → ON ACTIVATION: Immediately repay ALL debt (one-time, sell shares if needed)
        4. Execute monthly withdrawal - withdraw fixed amount (debt already cleared)
        5. Process dividends - paid on shares held overnight (reinvestment disabled during withdrawal mode)
        6. Charge interest - monthly on first trading day of new month
        7. Execute daily purchase - buy shares with cash and/or margin (SKIPPED during withdrawal mode)

        CRITICAL:
        - Margin call BEFORE dividends prevents "dividend resurrection" bug
        - Insolvency check prevents "zombie portfolio" bug
        - Threshold activation includes ONE-TIME complete debt payoff (clean slate for withdrawals)
        - Withdrawal BEFORE dividends to properly disable reinvestment
        - Dividend reinvestment stops during withdrawal mode (cash goes to fund withdrawals)
        - Daily investments stop during withdrawal mode (transition to decumulation phase)
        """
        # Normalize date to string format for consistency
        date_str = date if isinstance(date, str) else date.strftime('%Y-%m-%d')
        price = row['Close']

        # ==== STEP 1: Check Margin Requirements FIRST ====
        # Robinhood-style Margin Call and Forced Liquidation
        # This happens BEFORE dividends to prevent resurrection of insolvent portfolios
        if margin_ratio > 1.0 and borrowed_amount > 0 and total_shares > 0:
            # Capture state before margin call
            portfolio_value_before = total_shares * price
            shares_before = total_shares
            debt_before = borrowed_amount
            cash_before = current_balance if current_balance else 0
            equity_before = portfolio_value_before + cash_before - debt_before
            equity_ratio_before = calculate_equity_ratio(portfolio_value_before, current_balance, debt_before)

            # Execute margin call
            total_shares, current_balance, borrowed_amount, margin_call_triggered = execute_margin_call(
                total_shares, price, borrowed_amount, current_balance, maintenance_margin
            )

            if margin_call_triggered:
                margin_calls_triggered += 1
                margin_call_dates.append(date_str)

                # Capture state after margin call
                portfolio_value_after = total_shares * price
                shares_after = total_shares
                debt_after = borrowed_amount
                cash_after = current_balance if current_balance else 0
                equity_after = portfolio_value_after + cash_after - debt_after
                equity_ratio_after = calculate_equity_ratio(portfolio_value_after, current_balance, debt_after)

                shares_sold = shares_before - shares_after
                sale_proceeds = shares_sold * price
                debt_paid = debt_before - debt_after

                # Record detailed margin call information
                margin_call_details.append({
                    'date': date_str,
                    'price': price,
                    'equity_ratio_before': equity_ratio_before,
                    'equity_ratio_after': equity_ratio_after,
                    'portfolio_value_before': portfolio_value_before,
                    'portfolio_value_after': portfolio_value_after,
                    'shares_before': shares_before,
                    'shares_after': shares_after,
                    'shares_sold': shares_sold,
                    'sale_proceeds': sale_proceeds,
                    'debt_before': debt_before,
                    'debt_after': debt_after,
                    'debt_paid': debt_paid,
                    'cash_before': cash_before,
                    'cash_after': cash_after,
                    'equity_before': equity_before,
                    'equity_after': equity_after
                })

        # ==== STEP 2: Check Insolvency (STOP if account is dead) ====
        # Calculate current portfolio value after any margin call
        portfolio_value = total_shares * price

        # Check if account is insolvent (equity ≤ $0)
        # Only check after first day or when there's margin debt
        # (On first day, portfolio_value=0 would incorrectly trigger insolvency)
        if not first_day and check_insolvency(portfolio_value, current_balance, borrowed_amount):
            insolvency_detected = True
            insolvency_date = date_str
            # STOP SIMULATION - Account would be terminated on Robinhood
            # Record final metrics before breaking
            current_value = portfolio_value
            dates.append(date_str)
            invested_values.append(total_invested)
            portfolio_values.append(current_value)
            dividend_values.append(cumulative_dividends)
            balance_values.append(current_balance)
            borrowed_values.append(borrowed_amount)
            interest_values.append(total_interest_paid)
            net_portfolio_values.append(current_value - borrowed_amount)

            # Calculate final equity and leverage
            current_equity = current_value + (current_balance if current_balance else 0) - borrowed_amount
            current_leverage_ratio = (current_value / current_equity) if current_equity > 0 else 1.0
            leverage_values.append(current_leverage_ratio)

            # Track minimum equity (this IS the minimum since we're stopping)
            if current_equity < min_equity:
                min_equity = current_equity
                min_equity_date = date_str

            # Track peak equity (update if needed)
            if current_equity > peak_equity:
                peak_equity = current_equity

            avg_cost = total_cost_basis / total_shares if total_shares > 0 else 0
            average_cost_values.append(avg_cost)

            # Add withdrawal tracking (even though withdrawing stopped due to insolvency)
            withdrawal_mode_values.append(withdrawal_mode_active)
            withdrawal_amount_values.append(total_withdrawn)

            break  # EXIT LOOP - Simulation terminates

        # ==== STEP 3: Check Withdrawal Threshold ====
        # Check if net portfolio value has reached withdrawal threshold
        # Once activated, withdrawal mode never deactivates (one-way state)
        # When threshold is reached, immediately repay ALL debt before starting withdrawals
        if not withdrawal_mode_active and withdrawal_threshold is not None:
            current_net_value = (total_shares * price) + (current_balance if current_balance else 0) - borrowed_amount
            if current_net_value >= withdrawal_threshold:
                # Threshold reached! Repay all debt immediately (if any exists)
                if borrowed_amount > 0:
                    # Use execute_monthly_withdrawal with withdrawal_amount=0 to just repay debt
                    (total_shares, current_balance, borrowed_amount, total_cost_basis,
                     shares_sold, debt_repaid, _) = execute_monthly_withdrawal(
                        0,  # No withdrawal, just debt repayment
                        total_shares, price, borrowed_amount,
                        current_balance, total_cost_basis
                    )

                    # Track this one-time debt payoff event
                    if debt_repaid > 0:
                        withdrawal_details.append({
                            'date': date_str,
                            'event_type': 'threshold_debt_payoff',
                            'price': price,
                            'shares_sold': shares_sold,
                            'sale_proceeds': shares_sold * price,
                            'debt_repaid': debt_repaid,
                            'amount_withdrawn': 0,  # No withdrawal, just debt payoff
                            'cumulative_withdrawn': total_withdrawn,
                            'funded_by': 'share_sale'
                        })

                # Now activate withdrawal mode (debt is cleared)
                withdrawal_mode_active = True
                withdrawal_mode_start_date = date_str

        # ==== STEP 4: Execute Monthly Withdrawal ====
        # Process withdrawals monthly (on first trading day of each new month)
        if withdrawal_mode_active and monthly_withdrawal_amount is not None and monthly_withdrawal_amount > 0:
            try:
                current_date = pd.to_datetime(date_str)
                current_month = current_date.strftime('%Y-%m')
            except Exception as e:
                raise e

            # Execute withdrawal on first day of new month
            if current_month != last_withdrawal_month:
                # Track cash before withdrawal
                cash_before_withdrawal = current_balance if current_balance is not None else 0

                # Execute withdrawal
                (total_shares, current_balance, borrowed_amount, total_cost_basis,
                 shares_sold, debt_repaid, amount_withdrawn) = execute_monthly_withdrawal(
                    monthly_withdrawal_amount, total_shares, price, borrowed_amount,
                    current_balance, total_cost_basis
                )

                # Track withdrawal details (always track, even if $0 to show dividend-funded withdrawals)
                total_withdrawn += amount_withdrawn
                withdrawal_dates.append(date_str)
                withdrawal_details.append({
                    'date': date_str,
                    'event_type': 'withdrawal',
                    'requested_amount': monthly_withdrawal_amount,
                    'price': price,
                    'shares_sold': shares_sold,
                    'sale_proceeds': shares_sold * price,
                    'debt_repaid': debt_repaid,
                    'amount_withdrawn': amount_withdrawn,
                    'cash_before': cash_before_withdrawal,
                    'cash_after': current_balance if current_balance is not None else 0,
                    'cumulative_withdrawn': total_withdrawn,
                    'funded_by': 'dividends' if shares_sold == 0 and amount_withdrawn > 0 else 'share_sale' if shares_sold > 0 else 'partial'
                })

                last_withdrawal_month = current_month

        # ==== STEP 5: Process Dividends ====
        # Only process if account is still solvent
        # IMPORTANT: Disable dividend reinvestment during withdrawal mode
        # (dividends go to cash to help fund withdrawals)
        effective_reinvest = reinvest and (not withdrawal_mode_active)

        # Check for dividends on this day
        day_dividend = dividends.get(date_str)
        if day_dividend:
            cash_before_dividend = current_balance
            shares_added, total_cost_basis, current_balance, dividend_income = process_dividend(
                total_shares, day_dividend, price, effective_reinvest, current_balance, total_cost_basis
            )
            total_shares += shares_added
            cumulative_dividends += dividend_income

            # Track dividend income during withdrawal mode
            if withdrawal_mode_active and dividend_income > 0:
                withdrawal_details.append({
                    'date': date_str,
                    'event_type': 'dividend',
                    'dividend_per_share': day_dividend,
                    'shares_owned': total_shares - shares_added,  # Shares before dividend reinvestment
                    'dividend_income': dividend_income,
                    'cash_before': cash_before_dividend if cash_before_dividend is not None else 0,
                    'cash_after': current_balance if current_balance is not None else 0,
                    'cumulative_withdrawn': total_withdrawn
                })

        # ==== STEP 6: Charge Interest ====
        # Monthly interest charge (on the first day of each month)
        try:
            current_date = pd.to_datetime(date_str)
            current_month = current_date.strftime('%Y-%m')
        except Exception as e:
            raise e

        # Initialize last_interest_month on first iteration
        # Also charge interest on first day if already borrowed (for simulations starting mid-month)
        if last_interest_month is None:
            last_interest_month = current_month
            # If we already have borrowed amount on first day, charge interest for this month
            if borrowed_amount > 0:
                fed_rate = get_fed_funds_rate(date_str)
                current_balance, borrowed_amount, interest_charge = process_interest_charge(
                    borrowed_amount, fed_rate, current_balance
                )
                total_interest_paid += interest_charge

        # Check for month boundary crossing
        if current_month != last_interest_month and borrowed_amount > 0:
            # Charge one month's interest
            fed_rate = get_fed_funds_rate(date_str)
            current_balance, borrowed_amount, interest_charge = process_interest_charge(
                borrowed_amount, fed_rate, current_balance
            )
            total_interest_paid += interest_charge
            last_interest_month = current_month

        # ==== STEP 7: Execute Daily Purchase ====
        # Skip daily investments when withdrawal mode is active (decumulation phase)
        if not withdrawal_mode_active:
            # Check if we should invest today based on frequency
            should_invest, last_investment_month = should_invest_today(
                date, start_date, frequency, last_investment_month
            )

            daily_investment = 0
            if should_invest or first_day:
                daily_investment = amount

            if first_day:
                daily_investment += initial_amount
                first_day = False

            # Execute purchase using extracted function
            shares_bought, cash_used, margin_borrowed, actual_investment, principal_used, current_balance, borrowed_amount = execute_purchase(
                daily_investment, price, current_balance, borrowed_amount,
                margin_ratio, total_shares, available_principal
            )

            # Update portfolio and cost basis
            if actual_investment > 0:
                total_shares += shares_bought
                total_cost_basis += actual_investment

                # Update total_invested (External Cash Injected)
                # We track 'available_principal' to distinguish between user capital and recycled dividends/margin.
                if account_balance is None:
                    # Infinite cash mode: All cash used is considered new investment
                    total_invested += cash_used
                else:
                    # Constrained cash mode: Only count principal used (returned by execute_purchase)
                    available_principal -= principal_used
                    available_principal = max(0, available_principal)
                    total_invested += principal_used
        else:
            # In withdrawal mode: still clear first_day flag (needed for tracking)
            if first_day:
                first_day = False
        
        current_value = total_shares * price
        
        # Store raw values (not rounded) to preserve precision
        # Rounding will be done when returning final result
        dates.append(date_str)
        invested_values.append(total_invested)
        portfolio_values.append(current_value)
        dividend_values.append(cumulative_dividends)
        balance_values.append(current_balance)  # Can be None
        borrowed_values.append(borrowed_amount)
        interest_values.append(total_interest_paid)

        # Net portfolio value (equity) = portfolio value - borrowed amount
        net_portfolio_values.append(current_value - borrowed_amount)

        # Calculate current leverage ratio
        current_equity = current_value + (current_balance if current_balance else 0) - borrowed_amount
        current_leverage_ratio = (current_value / current_equity) if current_equity > 0 else 1.0
        leverage_values.append(current_leverage_ratio)

        # Track minimum equity (can go negative!)
        if current_equity < min_equity:
            min_equity = current_equity
            min_equity_date = date_str

        # Track peak equity for accurate drawdown calculation
        if current_equity > peak_equity:
            peak_equity = current_equity

        # Calculate Average Cost
        # Use total_cost_basis (all money spent) instead of total_invested (principal only)
        avg_cost = total_cost_basis / total_shares if total_shares > 0 else 0
        average_cost_values.append(avg_cost)

        # Track withdrawal mode and cumulative withdrawn amount
        withdrawal_mode_values.append(withdrawal_mode_active)
        withdrawal_amount_values.append(total_withdrawn)


    current_price = hist.iloc[-1]['Close']
    current_portfolio_value = total_shares * current_price
    
    # Calculate current leverage ratio
    current_portfolio_value = total_shares * current_price
    if margin_ratio > 1.0 and current_portfolio_value > 0:
        current_equity = current_portfolio_value + (current_balance if current_balance else 0) - borrowed_amount
        current_leverage = current_portfolio_value / current_equity if current_equity > 0 else 0
    else:
        current_leverage = 1.0

    # ==== CALCULATE ANALYTICS ====
    # Use net portfolio values (equity after debt) for analytics
    analytics_values = net_portfolio_values  # Already calculated in loop

    # Calculate daily returns
    daily_returns = calculate_daily_returns(analytics_values)

    # Calculate performance metrics
    # Use total_invested as baseline (not first day's value) for consistency with ROI
    final_equity = analytics_values[-1] if len(analytics_values) > 0 else 0
    num_days = len(dates)

    total_return_pct = calculate_total_return_percent(total_invested, final_equity)
    cagr = calculate_cagr(total_invested, final_equity, num_days)

    # Calculate risk metrics
    volatility = calculate_volatility(daily_returns)
    # Use CAGR-based Sharpe for DCA (avoids contribution contamination in daily returns)
    sharpe_ratio = calculate_sharpe_ratio_from_cagr(cagr / 100, volatility)
    max_dd, max_dd_peak_idx, max_dd_trough_idx = calculate_max_drawdown(analytics_values)

    # Calculate trading metrics
    win_rate = calculate_win_rate(daily_returns)
    best_day_pct, best_day_date, worst_day_pct, worst_day_date = calculate_best_worst_days(daily_returns, dates)

    # Calculate risk-adjusted return
    calmar = calculate_calmar_ratio(cagr, max_dd)

    # Round time series values for API response (raw values preserved during calculation)
    return {
        'dates': dates,
        'invested': [round(v, 2) for v in invested_values],
        'portfolio': [round(v, 2) for v in portfolio_values],
        'dividends': [round(v, 2) for v in dividend_values],
        'balance': [round(v, 2) if v is not None else None for v in balance_values],
        'borrowed': [round(v, 2) for v in borrowed_values],
        'interest': [round(v, 2) for v in interest_values],
        'net_portfolio': [round(v, 2) for v in net_portfolio_values],
        'leverage': [round(v, 2) for v in leverage_values],
        'average_cost': [round(v, 2) for v in average_cost_values],
        'margin_call_dates': margin_call_dates,
        'margin_call_details': margin_call_details,
        'withdrawal_mode': withdrawal_mode_values,
        'withdrawals': [round(v, 2) for v in withdrawal_amount_values],
        'withdrawal_dates': withdrawal_dates,
        'withdrawal_details': withdrawal_details,
        'actual_start_date': dates[0] if dates else None,
        'summary': {
            'total_invested': round(total_invested, 2),
            'current_value': round(current_portfolio_value, 2),
            'total_shares': round(total_shares, 4),
            'total_dividends': round(cumulative_dividends, 2),
            # ROI should be based on net equity (current value - borrowed) when using margin
            # Returns None if no capital invested (undefined ROI)
            'roi': round((((current_portfolio_value - borrowed_amount) - total_invested) / total_invested * 100), 2) if total_invested > 0 else None,
            'account_balance': round(current_balance, 2) if current_balance is not None else None,
            'total_borrowed': round(borrowed_amount, 2),
            'total_interest_paid': round(total_interest_paid, 2),
            'current_leverage': round(current_leverage, 2),
            'margin_calls': margin_calls_triggered,
            'net_portfolio_value': round(current_portfolio_value - borrowed_amount, 2),
            'average_cost': round(total_cost_basis / total_shares, 2) if total_shares > 0 else 0,
            # Insolvency tracking (Robinhood-accurate behavior)
            'insolvency_detected': insolvency_detected,
            'insolvency_date': insolvency_date,
            'min_equity_value': round(min_equity, 2) if min_equity != float('inf') else None,
            'min_equity_date': min_equity_date,
            'actual_max_drawdown': round((min_equity - peak_equity) / peak_equity, 4) if peak_equity > 0 else 0,
            # Withdrawal tracking
            'total_withdrawn': round(total_withdrawn, 2),
            'withdrawal_mode_active': withdrawal_mode_active,
            'withdrawal_mode_start_date': withdrawal_mode_start_date
        },
        'analytics': {
            # Performance metrics
            'total_return_pct': round(total_return_pct, 2),
            'cagr': round(cagr, 2),

            # Risk metrics
            'volatility': round(volatility, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'max_drawdown': round(max_dd, 2),
            'max_drawdown_peak_date': dates[max_dd_peak_idx] if max_dd_peak_idx < len(dates) else None,
            'max_drawdown_trough_date': dates[max_dd_trough_idx] if max_dd_trough_idx < len(dates) else None,

            # Trading metrics
            'win_rate': round(win_rate, 2),
            'best_day': round(best_day_pct, 2),
            'best_day_date': best_day_date,
            'worst_day': round(worst_day_pct, 2),
            'worst_day_date': worst_day_date,

            # Risk-adjusted metrics
            'calmar_ratio': round(calmar, 2),

            # Benchmark comparison (will be added if benchmark exists)
            'alpha': None,
            'beta': None
        }
    }

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    ticker = data.get('ticker')
    start_date = data.get('start_date')
    amount = float(data.get('amount'))
    initial_amount = float(data.get('initial_amount', 0))
    end_date = data.get('end_date')
    reinvest = data.get('reinvest', False)
    benchmark_ticker = data.get('benchmark_ticker')
    
    # Get account balance, default to None if not provided or empty
    account_balance_str = data.get('account_balance')
    account_balance = float(account_balance_str) if account_balance_str and account_balance_str != '' else None
    
    # Get margin parameters
    margin_ratio = float(data.get('margin_ratio', 1.0))
    maintenance_margin = float(data.get('maintenance_margin', DEFAULT_MAINTENANCE_MARGIN))

    # Get withdrawal parameters
    withdrawal_threshold_str = data.get('withdrawal_threshold')
    withdrawal_threshold = float(withdrawal_threshold_str) if withdrawal_threshold_str and withdrawal_threshold_str != '' else None

    monthly_withdrawal_str = data.get('monthly_withdrawal_amount')
    monthly_withdrawal_amount = float(monthly_withdrawal_str) if monthly_withdrawal_str and monthly_withdrawal_str != '' else None

    # Get frequency parameter (default to DAILY for backward compatibility)
    frequency = data.get('frequency', 'DAILY')

    if not ticker or not start_date or not amount:
        return jsonify({'error': 'Missing required fields'}), 400

    # Validate input ranges
    if amount < 0:
        return jsonify({'error': 'Daily amount must be non-negative'}), 400

    if initial_amount < 0:
        return jsonify({'error': 'Initial investment must be non-negative'}), 400

    if margin_ratio < 1.0 or margin_ratio > 2.0:
        return jsonify({'error': 'Margin ratio must be between 1.0 and 2.0'}), 400

    if maintenance_margin <= 0 or maintenance_margin >= 1.0:
        return jsonify({'error': 'Maintenance margin must be between 0 and 1 (exclusive)'}), 400

    if account_balance is not None and account_balance < 0:
        return jsonify({'error': 'Account balance must be non-negative'}), 400

    # Validate withdrawal parameters
    if withdrawal_threshold is not None and withdrawal_threshold < 0:
        return jsonify({'error': 'Withdrawal threshold must be non-negative'}), 400

    if monthly_withdrawal_amount is not None and monthly_withdrawal_amount < 0:
        return jsonify({'error': 'Monthly withdrawal amount must be non-negative'}), 400

    # Validate frequency parameter
    valid_frequencies = ['DAILY', 'WEEKLY', 'MONTHLY']
    if frequency not in valid_frequencies:
        return jsonify({'error': f'Invalid frequency. Must be one of: {", ".join(valid_frequencies)}'}), 400

    # If benchmark specified, find common date range to avoid synthetic data
    actual_start_date = start_date
    actual_end_date = end_date

    if benchmark_ticker:
        common_start, common_end, _, _ = find_common_date_range(ticker, benchmark_ticker, start_date, end_date)
        if common_start and common_end:
            actual_start_date = common_start
            actual_end_date = common_end
        else:
            return jsonify({'error': 'No common date range between portfolio and benchmark tickers'}), 404

    result = calculate_dca_core(ticker, actual_start_date, actual_end_date, amount, initial_amount, reinvest, account_balance=account_balance, margin_ratio=margin_ratio, maintenance_margin=maintenance_margin, withdrawal_threshold=withdrawal_threshold, monthly_withdrawal_amount=monthly_withdrawal_amount, frequency=frequency)

    if not result:
        return jsonify({'error': 'No data found for this ticker and date range'}), 404

    if benchmark_ticker:
        # Use same date range as portfolio (already determined to be common range)
        # Benchmark always uses NO MARGIN (ratio=1.0) for apples-to-apples comparison
        # Benchmark always uses DAILY frequency to isolate ticker performance from frequency effects
        # This ensures fair comparison regardless of user's chosen investment frequency
        benchmark_result = calculate_dca_core(benchmark_ticker, actual_start_date, actual_end_date, amount, initial_amount, reinvest, target_dates=result['dates'], account_balance=account_balance, margin_ratio=NO_MARGIN_RATIO, maintenance_margin=DEFAULT_MAINTENANCE_MARGIN, frequency='DAILY')
        if benchmark_result:
            result['benchmark'] = benchmark_result['portfolio']
            result['benchmark_summary'] = benchmark_result['summary']
            result['benchmark_analytics'] = benchmark_result['analytics']

            # Calculate alpha and beta vs benchmark
            portfolio_net_values = [result['net_portfolio'][i] for i in range(len(result['net_portfolio']))]
            benchmark_net_values = benchmark_result['net_portfolio']

            portfolio_daily_returns = calculate_daily_returns(portfolio_net_values)
            benchmark_daily_returns = calculate_daily_returns(benchmark_net_values)

            # Calculate beta from returns (correlation measure - still valid)
            _, beta = calculate_alpha_beta(portfolio_daily_returns, benchmark_daily_returns)

            # Calculate alpha from CAGR (avoids DCA contribution contamination)
            portfolio_cagr = result['analytics']['cagr'] / 100  # Convert to decimal
            benchmark_cagr = benchmark_result['analytics']['cagr'] / 100
            alpha = calculate_alpha_from_cagr(portfolio_cagr, benchmark_cagr, beta)

            # Add alpha/beta to main result analytics
            result['analytics']['alpha'] = round(alpha, 2)
            result['analytics']['beta'] = round(beta, 2)
        else:
            result['benchmark'] = []
            result['benchmark_summary'] = None
            result['benchmark_analytics'] = None

    # If using margin, also show no-margin comparison for same ticker
    if margin_ratio > 1.0:
        no_margin_result = calculate_dca_core(ticker, start_date, end_date, amount, initial_amount, reinvest, target_dates=result['dates'], account_balance=account_balance, margin_ratio=NO_MARGIN_RATIO, maintenance_margin=DEFAULT_MAINTENANCE_MARGIN)
        if no_margin_result:
            result['no_margin'] = no_margin_result['portfolio']
            result['no_margin_summary'] = no_margin_result['summary']
        else:
            result['no_margin'] = []
            result['no_margin_summary'] = None

    return jsonify(result)

@app.route('/search')
def search_ticker():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        data = response.json()
        
        suggestions = []
        if 'quotes' in data:
            for quote in data['quotes']:
                suggestions.append({
                    'symbol': quote.get('symbol'),
                    'name': quote.get('shortname', quote.get('longname', '')),
                    'type': quote.get('quoteType'),
                    'exch': quote.get('exchange')
                })
        return jsonify(suggestions)
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify([])

if __name__ == '__main__':
    # Production-ready configuration with environment variables
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)

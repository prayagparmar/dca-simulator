"""
Shared test fixtures and utilities for DCA Simulator tests.

This file provides reusable pytest fixtures and helper functions to eliminate
code duplication across test files. Previously, mock setup was duplicated
145 times across 17 test files (1,160 lines of redundant code).

Usage:
    from conftest import create_mock_stock_data

    def test_something():
        mock_ticker = create_mock_stock_data([100, 200, 300])
        with patch('app.yf.Ticker', return_value=mock_ticker):
            result = calculate_dca_core(...)
"""

import pandas as pd
from unittest.mock import MagicMock


def create_mock_stock_data(prices, dividends=None, start_date='2024-01-01'):
    """
    Create a mock yfinance Ticker object with historical price and dividend data.

    This eliminates the need to manually create MagicMock objects and DataFrames
    in every test. Replaces 8-10 lines of boilerplate with a single function call.

    Args:
        prices: List of closing prices (one per trading day)
        dividends: Optional dict of {date_str: dividend_amount} or pandas Series
        start_date: Starting date for the price series (default: '2024-01-01')

    Returns:
        MagicMock object configured to behave like yf.Ticker

    Examples:
        # Simple flat price, no dividends
        >>> mock = create_mock_stock_data([100, 100, 100])

        # Rising prices with dividends
        >>> mock = create_mock_stock_data(
        ...     [100, 110, 120],
        ...     dividends={'2024-01-02': 0.50}
        ... )
    """
    mock_ticker = MagicMock()

    # Create date range
    num_days = len(prices)
    dates = pd.date_range(start=start_date, periods=num_days, freq='D')

    # Create DataFrame with OHLCV data (yfinance format)
    # Use same price for Open/High/Low/Close for simplicity
    hist = pd.DataFrame({
        'Open': prices,
        'High': prices,
        'Low': prices,
        'Close': prices,
        'Volume': [1000000] * num_days  # Default 1M volume
    }, index=dates)

    # Convert index to string format (matches app.py behavior)
    hist.index = hist.index.strftime('%Y-%m-%d')

    mock_ticker.history.return_value = hist

    # Setup dividends
    if dividends is None:
        mock_ticker.dividends = pd.Series(dtype=float)
    elif isinstance(dividends, dict):
        # Convert dict to Series with datetime index
        div_dates = [pd.to_datetime(date) for date in dividends.keys()]
        div_values = list(dividends.values())
        mock_ticker.dividends = pd.Series(div_values, index=div_dates)
    elif isinstance(dividends, pd.Series):
        mock_ticker.dividends = dividends
    else:
        raise ValueError(f"dividends must be dict or pandas Series, got {type(dividends)}")

    return mock_ticker


def create_trending_stock(start_price=100, end_price=200, num_days=100, start_date='2024-01-01'):
    """
    Create a mock stock with linearly increasing price.

    Useful for testing DCA in trending markets.

    Args:
        start_price: Starting price
        end_price: Ending price
        num_days: Number of trading days
        start_date: Starting date

    Returns:
        MagicMock configured as trending stock

    Example:
        >>> mock = create_trending_stock(100, 200, 30)  # +3.45% daily
    """
    prices = [start_price + (end_price - start_price) * i / (num_days - 1) for i in range(num_days)]
    return create_mock_stock_data(prices, start_date=start_date)


def create_volatile_stock(base_price=100, volatility=0.20, num_days=100, start_date='2024-01-01', seed=42):
    """
    Create a mock stock with random price movements.

    Useful for testing DCA in volatile markets.

    Args:
        base_price: Average price
        volatility: Daily volatility (0.20 = 20%)
        num_days: Number of trading days
        start_date: Starting date
        seed: Random seed for reproducibility

    Returns:
        MagicMock configured as volatile stock

    Example:
        >>> mock = create_volatile_stock(100, 0.30, 50)  # High volatility
    """
    import random
    random.seed(seed)

    prices = [base_price]
    for _ in range(num_days - 1):
        change = random.gauss(0, volatility)
        prices.append(prices[-1] * (1 + change))

    return create_mock_stock_data(prices, start_date=start_date)


def create_dividend_stock(price=100, num_days=100, quarterly_dividend=0.50, start_date='2024-01-01'):
    """
    Create a mock stock with quarterly dividend payments.

    Useful for testing dividend reinvestment logic.

    Args:
        price: Stock price (constant)
        num_days: Number of trading days
        quarterly_dividend: Dividend amount paid per quarter
        start_date: Starting date

    Returns:
        MagicMock configured as dividend-paying stock

    Example:
        >>> mock = create_dividend_stock(100, 365, 0.75)  # $0.75 quarterly
    """
    prices = [price] * num_days
    dates = pd.date_range(start=start_date, periods=num_days, freq='D')

    # Find dates that are approximately 90 days apart (quarterly)
    dividends = {}
    for i in range(0, num_days, 90):
        if i < num_days:
            div_date = dates[i].strftime('%Y-%m-%d')
            dividends[div_date] = quarterly_dividend

    return create_mock_stock_data(prices, dividends=dividends, start_date=start_date)


def create_crash_scenario(peak_price=200, crash_pct=0.50, days_to_crash=10, days_after=30, start_date='2024-01-01'):
    """
    Create a mock stock that crashes dramatically.

    Useful for testing margin calls and insolvency detection.

    Args:
        peak_price: Price before crash
        crash_pct: Percentage drop (0.50 = 50% decline)
        days_to_crash: Number of days for crash to occur
        days_after: Days to continue after crash bottoms out
        start_date: Starting date

    Returns:
        MagicMock configured as crashing stock

    Example:
        >>> mock = create_crash_scenario(200, 0.70, 5, 10)  # 70% crash over 5 days
    """
    prices = []

    # Stable period before crash
    prices.extend([peak_price] * 10)

    # Crash period (linear decline)
    crash_low = peak_price * (1 - crash_pct)
    for i in range(days_to_crash):
        price = peak_price - (peak_price - crash_low) * (i + 1) / days_to_crash
        prices.append(price)

    # Recovery/stabilization period
    prices.extend([crash_low] * days_after)

    return create_mock_stock_data(prices, start_date=start_date)


# Convenience functions for common test scenarios
def flat_price_mock(price=100, days=100):
    """Quick helper for flat price with no dividends"""
    return create_mock_stock_data([price] * days)


def simple_trend_mock(start=100, end=200, days=100):
    """Quick helper for trending price"""
    return create_trending_stock(start, end, days)


def with_dividends_mock(price=100, days=100, dividend_per_share=0.50):
    """Quick helper for flat price with single dividend"""
    mid_date = pd.date_range(start='2024-01-01', periods=days, freq='D')[days // 2]
    return create_mock_stock_data(
        [price] * days,
        dividends={mid_date.strftime('%Y-%m-%d'): dividend_per_share}
    )

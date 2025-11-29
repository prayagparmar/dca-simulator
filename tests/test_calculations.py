import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import json
from app import app
from tests.conftest import create_mock_stock_data

class TestDCACalculation(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('app.yf.Ticker')
    def test_calculate_dca_no_dividends(self, mock_ticker):
        # Use shared helper to create mock (eliminates 8 lines of boilerplate)
        mock_ticker.return_value = create_mock_stock_data([100.0, 200.0, 300.0], start_date='2023-01-01')

        # Request
        payload = {
            'ticker': 'TEST',
            'start_date': '2023-01-01',
            'amount': 100,
            'reinvest': False
        }
        response = self.app.post('/calculate', json=payload)
        data = json.loads(response.data)

        # Verification
        # Day 1: Buy $100 @ 100 = 1 share. Total shares = 1.
        # Day 2: Buy $100 @ 200 = 0.5 share. Total shares = 1.5.
        # Day 3: Buy $100 @ 300 = 0.3333 share. Total shares = 1.8333.
        
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(data['summary']['total_invested'], 300.0)
        self.assertAlmostEqual(data['summary']['total_shares'], 1.8333, places=4)
        self.assertEqual(data['summary']['total_dividends'], 0.0)
        # Current value = 1.8333 * 300 = 550
        self.assertAlmostEqual(data['summary']['current_value'], 550.0, places=1)

    @patch('app.yf.Ticker')
    def test_calculate_dca_with_dividends(self, mock_ticker):
        # Use shared helper with dividends (eliminates 11 lines of boilerplate)
        mock_ticker.return_value = create_mock_stock_data(
            [100.0, 100.0, 100.0],
            dividends={'2023-01-02': 10.0},  # $10 dividend on Day 2
            start_date='2023-01-01'
        )

        # Request
        payload = {
            'ticker': 'TEST',
            'start_date': '2023-01-01',
            'amount': 100,
            'reinvest': True
        }
        response = self.app.post('/calculate', json=payload)
        data = json.loads(response.data)

        # Verification
        # Day 1: Buy $100 @ 100 = 1 share. Total shares = 1.
        # Day 2: 
        #   - Dividend: 1 share * $10 = $10.
        #   - Reinvest: $10 / 100 = 0.1 share.
        #   - Regular Buy: $100 / 100 = 1 share.
        #   - Total shares = 1 + 0.1 + 1 = 2.1.
        # Day 3: Buy $100 @ 100 = 1 share. Total shares = 3.1.
        
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(data['summary']['total_invested'], 300.0) # Dividends don't count as invested cash
        self.assertAlmostEqual(data['summary']['total_shares'], 3.1, places=4)
        self.assertAlmostEqual(data['summary']['total_dividends'], 10.0)
        self.assertAlmostEqual(data['summary']['current_value'], 310.0, places=1)

    @patch('app.yf.Ticker')
    def test_calculate_dca_with_initial_investment(self, mock_ticker):
        # Mock stock data
        mock_stock = MagicMock()
        dates = pd.date_range(start='2023-01-01', periods=3, freq='D')
        # Prices: 100, 200, 300
        data = {'Close': [100.0, 200.0, 300.0]}
        hist = pd.DataFrame(data, index=dates)
        mock_stock.history.return_value = hist
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        # Request
        payload = {
            'ticker': 'TEST',
            'start_date': '2023-01-01',
            'amount': 100,
            'initial_amount': 1000,
            'reinvest': False
        }
        response = self.app.post('/calculate', json=payload)
        data = json.loads(response.data)

        # Verification
        # Day 1: Buy ($1000 + $100) @ 100 = 11 shares. Total shares = 11.
        # Day 2: Buy $100 @ 200 = 0.5 share. Total shares = 11.5.
        # Day 3: Buy $100 @ 300 = 0.3333 share. Total shares = 11.8333.
        
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(data['summary']['total_invested'], 1300.0)
        self.assertAlmostEqual(data['summary']['total_shares'], 11.8333, places=4)
        # Current value = 11.8333 * 300 = 3550
        self.assertAlmostEqual(data['summary']['current_value'], 3550.0, places=1)
        
    @patch('app.yf.Ticker')
    def test_calculate_dca_with_end_date(self, mock_ticker):
        # Mock stock data
        mock_stock = MagicMock()
        dates = pd.date_range(start='2023-01-01', periods=5, freq='D')
        # Prices: 100, 200, 300, 400, 500
        data = {'Close': [100.0, 200.0, 300.0, 400.0, 500.0]}
        hist = pd.DataFrame(data, index=dates)
        
        # Mock history call to filter by end date
        def side_effect(start=None, end=None, **kwargs):
            if end:
                return hist[hist.index < end]
            return hist
            
        mock_stock.history.side_effect = side_effect
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        # Request
        payload = {
            'ticker': 'TEST',
            'start_date': '2023-01-01',
            'end_date': '2023-01-04', # Should include up to Jan 3rd (exclusive of Jan 4th usually, or inclusive depending on impl)
            # In my app.py I pass end directly to yfinance. yfinance end is exclusive.
            # So 2023-01-04 means data up to 2023-01-03.
            # Dates: Jan 1, Jan 2, Jan 3. (3 days)
            'amount': 100,
            'reinvest': False
        }
        response = self.app.post('/calculate', json=payload)
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['dates']), 3)
        self.assertEqual(data['dates'][-1], '2023-01-03')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['dates']), 3)
        self.assertEqual(data['dates'][-1], '2023-01-03')

    @patch('app.yf.Ticker')
    def test_calculate_dca_with_benchmark(self, mock_ticker):
        # Mock stock data
        mock_stock = MagicMock()
        dates = pd.date_range(start='2023-01-01', periods=3, freq='D')
        data = {'Close': [100.0, 200.0, 300.0]}
        hist = pd.DataFrame(data, index=dates)
        mock_stock.history.return_value = hist
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        # Request
        payload = {
            'ticker': 'TEST',
            'start_date': '2023-01-01',
            'amount': 100,
            'benchmark_ticker': 'SPY'
        }
        response = self.app.post('/calculate', json=payload)
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        # Since we mocked Ticker to return the same data for any ticker,
        # the benchmark (SPY) result should be identical to the main ticker result.
        self.assertIn('benchmark', data)
        self.assertEqual(data['benchmark'], data['portfolio'])
        
        # Verify benchmark summary
        self.assertIn('benchmark_summary', data)
        self.assertIsNotNone(data['benchmark_summary'])
        self.assertEqual(data['benchmark_summary']['current_value'], data['summary']['current_value'])

    @patch('app.yf.Ticker')
    def test_calculate_dca_benchmark_alignment(self, mock_ticker):
        # Mock main ticker (Crypto - 7 days)
        mock_stock_main = MagicMock()
        dates_main = pd.date_range(start='2023-01-01', end='2023-01-07', freq='D') # 7 days
        mock_stock_main.history.return_value = pd.DataFrame({
            'Close': [100] * len(dates_main)
        }, index=dates_main)
        mock_stock_main.dividends = pd.Series(dtype=float)
        
        # Mock benchmark ticker (Stock - 5 days, missing weekends)
        mock_stock_bench = MagicMock()
        dates_bench = pd.bdate_range(start='2023-01-01', end='2023-01-07') # 5 days
        mock_stock_bench.history.return_value = pd.DataFrame({
            'Close': [200] * len(dates_bench)
        }, index=dates_bench)
        mock_stock_bench.dividends = pd.Series(dtype=float)
        
        # Configure mock to return different stocks based on ticker
        def side_effect(ticker):
            if ticker == 'BTC-USD':
                return mock_stock_main
            else:
                return mock_stock_bench
        
        mock_ticker.side_effect = side_effect

        payload = {
            'ticker': 'BTC-USD',
            'start_date': '2023-01-01',
            'end_date': '2023-01-07',
            'amount': 100,
            'benchmark_ticker': 'SPY'
        }
        response = self.app.post('/calculate', json=payload)
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['dates']), 7) # Main ticker has 7 days
        self.assertEqual(len(data['benchmark']), 7) # Benchmark should be aligned to 7 days
        
        # Verify forward fill: 
        # Jan 1 (Sun) - Main: 100. Bench: Should match Jan 2 or be backfilled? 
        # Our logic: ffill then bfill.
        # Jan 1 is Sunday. Bench starts Jan 2 (Monday).
        # So Jan 1 should be backfilled from Jan 2.
        # Jan 7 (Sat) - Main: 100. Bench: Should be ffilled from Jan 6 (Fri).
        
        self.assertIsNotNone(data['benchmark'][0]) # Jan 1
        self.assertIsNotNone(data['benchmark'][-1]) # Jan 7

    @patch('app.yf.Ticker')
    def test_calculate_dca_benchmark_alignment_reverse(self, mock_ticker):
        # Test Case: Main is Stock (5 days), Benchmark is Crypto (7 days)
        # We expect the benchmark to be filtered down to match the stock's 5 days.
        
        # Mock main ticker (Stock - 5 days)
        mock_stock_main = MagicMock()
        dates_main = pd.bdate_range(start='2023-01-01', end='2023-01-07') # 5 days (Mon-Fri)
        mock_stock_main.history.return_value = pd.DataFrame({
            'Close': [100] * len(dates_main)
        }, index=dates_main)
        mock_stock_main.dividends = pd.Series(dtype=float)
        
        # Mock benchmark ticker (Crypto - 7 days)
        mock_stock_bench = MagicMock()
        dates_bench = pd.date_range(start='2023-01-01', end='2023-01-07', freq='D') # 7 days
        mock_stock_bench.history.return_value = pd.DataFrame({
            'Close': [200] * len(dates_bench)
        }, index=dates_bench)
        mock_stock_bench.dividends = pd.Series(dtype=float)
        
        # Configure mock
        def side_effect(ticker):
            if ticker == 'AAPL':
                return mock_stock_main
            else:
                return mock_stock_bench
        
        mock_ticker.side_effect = side_effect

        payload = {
            'ticker': 'AAPL',
            'start_date': '2023-01-01',
            'end_date': '2023-01-07',
            'amount': 100,
            'benchmark_ticker': 'BTC-USD'
        }
        response = self.app.post('/calculate', json=payload)
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['dates']), 5) # Main ticker has 5 days
        self.assertEqual(len(data['benchmark']), 5) # Benchmark should be aligned to 5 days
        
        # Verify that we didn't get None for the valid days
        self.assertIsNotNone(data['benchmark'][0])
        
    @patch('app.yf.Ticker')
    def test_calculate_dca_empty_data(self, mock_ticker):
        mock_stock = MagicMock()
        mock_stock.history.return_value = pd.DataFrame()
        mock_ticker.return_value = mock_stock

        payload = {
            'ticker': 'INVALID',
            'start_date': '2023-01-01',
            'amount': 100
        }
        response = self.app.post('/calculate', json=payload)
        self.assertEqual(response.status_code, 404)

    @patch('app.requests.get')
    def test_search_ticker(self, mock_get):
        # Mock Yahoo Finance API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'quotes': [
                {'symbol': 'AAPL', 'shortname': 'Apple Inc.', 'quoteType': 'EQUITY', 'exchange': 'NMS'},
                {'symbol': 'AAP', 'shortname': 'Advance Auto Parts', 'quoteType': 'EQUITY', 'exchange': 'NYQ'}
            ]
        }
        mock_get.return_value = mock_response

        response = self.app.get('/search?q=AAP')
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['symbol'], 'AAPL')
        self.assertEqual(data[0]['name'], 'Apple Inc.')
        
    def test_search_ticker_empty(self):
        response = self.app.get('/search?q=')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data, [])

    @patch('app.yf.Ticker')
    def test_calculate_dca_mixed_dividends(self, mock_ticker):
        # Test Case: Main ticker (No Divs) vs Benchmark (Has Divs)
        # Reinvest = True
        # Expectation: Benchmark should have more shares/value than if Reinvest was False (or if it had no divs)
        
        # Mock Main Ticker (No Dividends)
        mock_stock_main = MagicMock()
        # Use date_range with periods=5 to guarantee 5 days
        dates = pd.date_range(start='2023-01-01', periods=5, freq='D')
        mock_stock_main.history.return_value = pd.DataFrame({'Close': [100] * 5}, index=dates)
        mock_stock_main.dividends = pd.Series(dtype=float) # Empty dividends
        
        # Mock Benchmark Ticker (Has Dividends)
        mock_stock_bench = MagicMock()
        mock_stock_bench.history.return_value = pd.DataFrame({'Close': [100] * 5}, index=dates)
        # Dividend on day 3
        mock_stock_bench.dividends = pd.Series([10.0], index=[dates[2]]) 
        
        def side_effect(ticker):
            if ticker == 'NODIV':
                return mock_stock_main
            else:
                return mock_stock_bench
        mock_ticker.side_effect = side_effect

        payload = {
            'ticker': 'NODIV',
            'start_date': '2023-01-01',
            'end_date': '2023-01-05',
            'amount': 100,
            'benchmark_ticker': 'DIVS',
            'reinvest': True
        }
        
        response = self.app.post('/calculate', json=payload)
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        
        # Main ticker: 5 days * $100 / $100 = 5 shares. No divs.
        self.assertEqual(data['summary']['total_shares'], 5.0)
        self.assertEqual(data['summary']['total_dividends'], 0.0)
        
        # Benchmark ticker:
        # Day 1: Buy 1 share (Total 1)
        # Day 2: Buy 1 share (Total 2)
        # Day 3: Divs! 2 shares * $10 = $20. Reinvest $20 / $100 = 0.2 shares. Buy 1 share. (Total 3.2)
        # Day 4: Buy 1 share (Total 4.2)
        # Day 5: Buy 1 share (Total 5.2)
        
        self.assertIn('benchmark_summary', data)
        self.assertGreater(data['benchmark_summary']['total_shares'], 5.0)
        self.assertAlmostEqual(data['benchmark_summary']['total_shares'], 5.2)
        self.assertEqual(data['benchmark_summary']['total_dividends'], 20.0)

    @patch('app.yf.Ticker')
    def test_calculate_dca_account_balance_cap(self, mock_ticker):
        # Test Case: Account Balance Cap
        # Initial Balance: $250
        # Daily Amount: $100
        # CORRECTED BEHAVIOR (bug fix): Invests all available cash
        # Day 1: Invest $100. Balance $150.
        # Day 2: Invest $100. Balance $50.
        # Day 3: Invest $50 (all remaining). Balance $0.
        # Day 4: Invest $0 (no cash). Balance $0.
        # Day 5: Invest $0 (no cash). Balance $0.

        mock_stock = MagicMock()
        dates = pd.date_range(start='2023-01-01', periods=5, freq='D') # 5 days
        mock_stock.history.return_value = pd.DataFrame({'Close': [100] * 5}, index=dates)
        mock_stock.dividends = pd.Series(dtype=float)
        mock_ticker.return_value = mock_stock

        payload = {
            'ticker': 'CAP',
            'start_date': '2023-01-01',
            'end_date': '2023-01-05',
            'amount': 100,
            'account_balance': 250
        }

        response = self.app.post('/calculate', json=payload)
        data = json.loads(response.data)

        self.assertEqual(response.status_code, 200)

        # Total Invested should be exactly $250 (all principal used)
        self.assertEqual(data['summary']['total_invested'], 250.0)

        # Total Shares:
        # Day 1: $100 / $100 = 1 share
        # Day 2: $100 / $100 = 1 share
        # Day 3: $50 / $100 = 0.5 shares
        # Total = 2.5 shares
        self.assertEqual(data['summary']['total_shares'], 2.5)

        # Verify Balance History
        # Day 1: Start 250 - 100 = 150
        # Day 2: 150 - 100 = 50
        # Day 3: 50 - 50 = 0
        # Day 4: 0
        # Day 5: 0
        self.assertIn('balance', data)
        self.assertEqual(data['balance'][0], 150.0)
        self.assertEqual(data['balance'][1], 50.0)
        self.assertEqual(data['balance'][2], 0.0)
        self.assertEqual(data['balance'][3], 0.0)
        self.assertEqual(data['balance'][4], 0.0)

    @patch('app.yf.Ticker')
    def test_calculate_dca_dividends_to_balance(self, mock_ticker):
        # Test Case: Dividends to Balance (Reinvest = False)
        # Initial Balance: $200
        # Daily Amount: $100
        # Day 1: Invest $100. Balance $100. Shares = 1.
        # Day 2: Dividend $10/share. Income $10. Balance $100 + $10 = $110. Invest $100. Balance $10.
        # Day 3: Invest $0 (Wait). Balance $10.
        
        mock_stock = MagicMock()
        dates = pd.date_range(start='2023-01-01', periods=3, freq='D')
        mock_stock.history.return_value = pd.DataFrame({'Close': [100] * 3}, index=dates)
        # Dividend on Day 2
        mock_stock.dividends = pd.Series([10.0], index=[dates[1]])
        mock_ticker.return_value = mock_stock

        payload = {
            'ticker': 'DIVBAL',
            'start_date': '2023-01-01',
            'end_date': '2023-01-03',
            'amount': 100,
            'account_balance': 200,
            'reinvest': False
        }
        
        response = self.app.post('/calculate', json=payload)
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        
        # Verify Balance History
        # Day 1: Start 200 - 100 = 100.
        self.assertEqual(data['balance'][0], 100.0)
        
        # Day 2: 
        # Div Income = 1 share * $10 = $10. 
        # Current Balance = 100 + 10 = 110.
        # Invest 100.
        # Current Balance = 110 - 100 = 10.
        self.assertEqual(data['balance'][1], 10.0)
        
        # Day 3:
        # Balance 10 < Amount 100. CORRECTED: Invest all $10 remaining.
        # Current Balance = 0.
        self.assertEqual(data['balance'][2], 0.0)

        # Total Invested: 100 + 100 = 200 (principal only)
        self.assertEqual(data['summary']['total_invested'], 200.0)

        # Total Dividends: 10
        self.assertEqual(data['summary']['total_dividends'], 10.0)

        # Ending Balance: All cash invested (including dividend)
        self.assertEqual(data['summary']['account_balance'], 0.0)

    @patch('app.yf.Ticker')
    def test_calculate_dca_dividend_accumulation(self, mock_ticker):
        # Test Case: Dividend Accumulation triggering a buy
        # Initial Balance: $0
        # Daily Amount: $100
        # Price: $100
        # Day 1: No buy (Bal 0).
        # Day 2: Div $50. Bal 50. No buy.
        # Day 3: Div $50. Bal 100. Buy $100! Bal 0.
        
        # To make this work, we need shares to generate dividends.
        # So let's start with Initial Investment of $1000 (10 shares).
        # Daily Amount: $100.
        # Account Balance: $0 (after initial investment is handled separately? No, initial investment usually comes from outside or is part of the first day check).
        # In our app.py: "if first_day: daily_investment += initial_amount".
        # And "if current_balance >= daily_investment:".
        # So if we want initial investment to happen, we need balance for it.
        
        # Let's try:
        # Account Balance: $100.
        # Initial Investment: $0.
        # Daily Amount: $100.
        # Day 1: Buy $100. Shares = 1. Bal = 0.
        # Day 2: Div $50. Bal 50. No buy.
        # Day 3: Div $50. Bal 100. Buy $100. Bal 0. Shares = 2.
        
        mock_stock = MagicMock()
        dates = pd.date_range(start='2023-01-01', periods=3, freq='D')
        mock_stock.history.return_value = pd.DataFrame({'Close': [100] * 3}, index=dates)
        
        # Dividends on Day 2 and Day 3
        # Day 2: $50/share. 1 share * 50 = 50.
        # Day 3: $50/share. 1 share * 50 = 50.
        mock_stock.dividends = pd.Series([50.0, 50.0], index=[dates[1], dates[2]])
        mock_ticker.return_value = mock_stock

        payload = {
            'ticker': 'ACCUM',
            'start_date': '2023-01-01',
            'end_date': '2023-01-03',
            'amount': 100,
            'account_balance': 100,
            'reinvest': False
        }
        
        response = self.app.post('/calculate', json=payload)
        data = json.loads(response.data)
        
        self.assertEqual(response.status_code, 200)
        
        # Day 1: Buy 100. Bal 0. Shares 1.
        self.assertEqual(data['balance'][0], 0.0)

        # Day 2: Div 50 (1 share * $50). Bal 50. CORRECTED: Invest $50. Bal 0. Shares 1.5.
        self.assertEqual(data['balance'][1], 0.0)

        # Day 3: Div 75 (1.5 shares * $50). Bal 75. Invest $75. Bal 0. Shares 2.25.
        self.assertEqual(data['balance'][2], 0.0)

        # Total Invested: Capped at account_balance (100) - principal only, dividends excluded
        self.assertEqual(data['summary']['total_invested'], 100.0)
        # Total Shares: 1 + 0.5 + 0.75 = 2.25 shares
        self.assertAlmostEqual(data['summary']['total_shares'], 2.25, places=2)

if __name__ == '__main__':
    unittest.main()

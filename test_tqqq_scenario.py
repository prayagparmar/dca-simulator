"""
Test the actual TQQQ scenario that the user reported.

User's Parameters:
- Stock: TQQQ
- Date Range: 08/01/2019 to present
- Initial Investment: $350,000
- Account Balance: $350,000
- Daily Amount: $5,000
- Margin Ratio: 2X
- Maintenance Margin: 25%
- Reinvest Dividends: True
- Benchmark: SPY

Expected Behavior (AFTER FIX):
- Portfolio should TERMINATE when equity ≤ $0
- Should NOT show -100% drawdown with portfolio still alive
- Should display actual insolvency detection

Previous Behavior (BEFORE FIX - BUG):
- Max Drawdown: -100.00%
- Margin Calls: Only 3
- Portfolio Status: Still alive with $896K value
- This was WRONG!
"""

from app import calculate_dca_core
import json

print("=" * 80)
print("TESTING TQQQ SCENARIO - User's Exact Parameters")
print("=" * 80)

# Run simulation with user's exact parameters
result = calculate_dca_core(
    ticker='TQQQ',
    start_date='2019-08-01',
    end_date='2024-11-01',  # Recent date
    amount=5000,
    initial_amount=350000,
    reinvest=True,
    account_balance=350000,
    margin_ratio=2.0,
    maintenance_margin=0.25
)

# Display summary
print("\n" + "=" * 80)
print("SIMULATION RESULTS")
print("=" * 80)

print(f"\n📊 PORTFOLIO SUMMARY:")
print(f"   Total Invested:        ${result['summary']['total_invested']:,.2f}")
print(f"   Current Value:         ${result['summary']['current_value']:,.2f}")
print(f"   Total Shares:          {result['summary']['total_shares']:.4f}")
print(f"   Net Portfolio Value:   ${result['summary']['net_portfolio_value']:,.2f}")
print(f"   ROI:                   {result['summary']['roi']:.2f}%" if result['summary']['roi'] else "   ROI:                   N/A")

print(f"\n💰 MARGIN STATUS:")
print(f"   Total Borrowed:        ${result['summary']['total_borrowed']:,.2f}")
print(f"   Total Interest Paid:   ${result['summary']['total_interest_paid']:,.2f}")
print(f"   Current Leverage:      {result['summary']['current_leverage']:.2f}x")
print(f"   Margin Calls:          {result['summary']['margin_calls']}")

print(f"\n💵 DIVIDENDS:")
print(f"   Total Dividends:       ${result['summary']['total_dividends']:,.2f}")

print(f"\n⚠️  INSOLVENCY STATUS (NEW!):")
print(f"   Insolvency Detected:   {result['summary']['insolvency_detected']}")
if result['summary']['insolvency_detected']:
    print(f"   🔴 ACCOUNT TERMINATED on {result['summary']['insolvency_date']}")
    print(f"   Minimum Equity:        ${result['summary']['min_equity_value']:,.2f}")
    print(f"   Min Equity Date:       {result['summary']['min_equity_date']}")
    print(f"   Actual Max Drawdown:   {result['summary']['actual_max_drawdown']:.2%}")
else:
    print(f"   ✅ Account still solvent")
    print(f"   Minimum Equity:        ${result['summary']['min_equity_value']:,.2f}")
    print(f"   Min Equity Date:       {result['summary']['min_equity_date']}")

print(f"\n📈 ANALYTICS:")
print(f"   Total Return:          {result['analytics']['total_return_pct']:.2f}%")
print(f"   CAGR:                  {result['analytics']['cagr']:.2f}%")
print(f"   Max Drawdown:          {result['analytics']['max_drawdown']:.2f}%")
print(f"   Sharpe Ratio:          {result['analytics']['sharpe_ratio']:.2f}")
print(f"   Volatility:            {result['analytics']['volatility']:.2f}%")

print(f"\n📅 TIMELINE:")
print(f"   Start Date:            {result['actual_start_date']}")
print(f"   End Date:              {result['dates'][-1]}")
print(f"   Trading Days:          {len(result['dates'])}")

print("\n" + "=" * 80)
print("VERIFICATION")
print("=" * 80)

# Check if the bug is fixed
if result['summary']['insolvency_detected']:
    print("✅ FIX VERIFIED: Insolvency detected! Simulation terminated correctly.")
    print("   Portfolio no longer shows 'zombie' behavior.")
    print(f"   Account was terminated on {result['summary']['insolvency_date']}")
else:
    if result['analytics']['max_drawdown'] <= -100:
        print("⚠️  WARNING: Portfolio shows severe drawdown but no insolvency!")
        print("   This might indicate the bug still exists.")
    else:
        print("✅ Portfolio survived without insolvency (legitimate scenario)")

print("\n" + "=" * 80)

# Save detailed results to file for inspection
with open('/Users/prayagparmar/Downloads/finance/tqqq_results.json', 'w') as f:
    json.dump({
        'summary': result['summary'],
        'analytics': result['analytics'],
        'dates_count': len(result['dates']),
        'first_date': result['dates'][0] if result['dates'] else None,
        'last_date': result['dates'][-1] if result['dates'] else None
    }, f, indent=2)

print("Detailed results saved to: tqqq_results.json")
print("=" * 80)

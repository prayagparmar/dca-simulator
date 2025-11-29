// Autocomplete logic
function setupAutocomplete(inputId, suggestionsId) {
    const input = document.getElementById(inputId);
    const suggestionsBox = document.getElementById(suggestionsId);
    let debounceTimer;

    input.addEventListener('input', function () {
        const query = this.value;
        clearTimeout(debounceTimer);

        if (query.length < 2) {
            suggestionsBox.style.display = 'none';
            return;
        }

        debounceTimer = setTimeout(() => {
            fetch(`/search?q=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(data => {
                    suggestionsBox.innerHTML = '';
                    if (data.length > 0) {
                        data.forEach(item => {
                            const div = document.createElement('div');
                            div.className = 'suggestion-item';
                            div.innerHTML = `
                                    <span class="suggestion-symbol">${item.symbol}</span>
                                    <span class="suggestion-name">${item.name}</span>
                                    <span class="suggestion-type">${item.type}</span>
                                `;
                            div.addEventListener('click', function () {
                                input.value = item.symbol;
                                suggestionsBox.style.display = 'none';
                            });
                            suggestionsBox.appendChild(div);
                        });
                        suggestionsBox.style.display = 'block';
                    } else {
                        suggestionsBox.style.display = 'none';
                    }
                });
        }, 300);
    });

    // Close suggestions when clicking outside
    document.addEventListener('click', function (e) {
        if (e.target !== input && e.target !== suggestionsBox) {
            suggestionsBox.style.display = 'none';
        }
    });
}

setupAutocomplete('ticker', 'ticker-suggestions');
setupAutocomplete('benchmark', 'benchmark-suggestions');

// Number formatting logic
function formatNumber(value) {
    if (!value) return '';
    // Remove existing commas and non-numeric chars (except decimal)
    const cleanVal = value.replace(/[^\d.]/g, '');
    if (!cleanVal) return '';

    // Split decimal
    const parts = cleanVal.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');

    return parts.join('.');
}

function setupNumberFormatting(inputId) {
    const input = document.getElementById(inputId);
    input.addEventListener('input', function (e) {
        // Store cursor position relative to end to handle insertion
        const val = this.value;
        const oldLength = val.length;
        const oldIdx = this.selectionStart;

        this.value = formatNumber(val);

        // Simple cursor handling: if length changed, adjust
        // This is a basic implementation; perfect cursor tracking is complex
    });
}

setupNumberFormatting('initial-amount');
setupNumberFormatting('account-balance');
setupNumberFormatting('amount');
setupNumberFormatting('withdrawal-threshold');
setupNumberFormatting('monthly-withdrawal');

document.getElementById('calculate-btn').addEventListener('click', async () => {
    const ticker = document.getElementById('ticker').value;
    const startDate = document.getElementById('start-date').value;
    const endDate = document.getElementById('end-date').value;
    const amount = document.getElementById('amount').value;
    const initialAmount = document.getElementById('initial-amount').value;

    if (!ticker || !startDate || !amount) {
        alert('Please fill in all fields');
        return;
    }

    const reinvest = document.getElementById('reinvest').checked;
    const benchmarkTicker = document.getElementById('benchmark').value;
    const accountBalance = document.getElementById('account-balance').value;
    const marginRatio = document.getElementById('margin-ratio').value;
    const maintenanceMargin = document.getElementById('maintenance-margin').value;
    const withdrawalThreshold = document.getElementById('withdrawal-threshold').value;
    const monthlyWithdrawal = document.getElementById('monthly-withdrawal').value;
    const frequency = document.getElementById('frequency').value || 'DAILY';

    const calculateBtn = document.getElementById('calculate-btn');
    calculateBtn.disabled = true;
    calculateBtn.textContent = 'Calculating...';

    try {
        const response = await fetch('/calculate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                ticker: ticker,
                start_date: startDate,
                amount: amount.replace(/,/g, ''),
                initial_amount: initialAmount.replace(/,/g, ''),
                end_date: endDate,
                reinvest: reinvest,
                benchmark_ticker: benchmarkTicker,
                account_balance: accountBalance.replace(/,/g, ''),
                margin_ratio: marginRatio,
                maintenance_margin: parseFloat(maintenanceMargin) / 100,
                withdrawal_threshold: withdrawalThreshold.replace(/,/g, ''),
                monthly_withdrawal_amount: monthlyWithdrawal.replace(/,/g, ''),
                frequency: frequency
            })
        });

        if (!response.ok) {
            const err = await response.json();
            alert(err.error || 'An error occurred');
            return;
        }

        const data = await response.json();
        renderResults(data, benchmarkTicker);
    } catch (error) {
        console.error(error);
        alert('Failed to fetch data');
    } finally {
        calculateBtn.disabled = false;
        calculateBtn.textContent = 'Calculate';
    }
});

let chartInstance = null;

function renderResults(data, benchmarkTicker) {
    // Get ticker value for chart labels
    const ticker = document.getElementById('ticker').value;

    // Check for start date warning
    const requestedStartDate = document.getElementById('start-date').value;
    const actualStartDate = data.actual_start_date;
    const warningContainer = document.getElementById('warning-container');

    // Build warnings HTML
    let warningsHTML = '';

    // Start date mismatch warning
    if (actualStartDate && requestedStartDate && actualStartDate !== requestedStartDate) {
        warningsHTML += `
            <div class="warning-message">
                <strong>⚠️ Start Date Mismatch:</strong>
                Requested start date was <strong>${requestedStartDate}</strong>,
                but data is only available from <strong>${actualStartDate}</strong>.
                The comparison uses the actual start date.
            </div>
        `;
    }

    // Insolvency warning (CRITICAL)
    if (data.summary && data.summary.insolvency_detected) {
        warningsHTML += `
            <div class="warning-message" style="background-color: #4a1c1c; border-left: 4px solid #dc2626; margin-top: ${warningsHTML ? '10px' : '0'};">
                <strong>🔴 ACCOUNT TERMINATED</strong><br>
                <div style="margin-top: 8px;">
                    <strong>Insolvency Date:</strong> ${data.summary.insolvency_date}<br>
                    <strong>Reason:</strong> Equity fell to $0 or below (Debt exceeded Assets)<br>
                    <strong>Minimum Equity:</strong> $${(data.summary.min_equity_value || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}<br>
                    <br>
                    <em>On Robinhood, your account would have been terminated on this date. The simulation stopped to match real-world margin trading behavior.</em>
                </div>
            </div>
        `;
    }

    // Display warnings or hide container
    if (warningsHTML) {
        warningContainer.innerHTML = warningsHTML;
        warningContainer.style.display = 'block';
    } else {
        warningContainer.style.display = 'none';
    }

    document.getElementById('results-area').style.display = 'block';

    // ==== HERO METRICS ====
    const analytics = data.analytics || {};
    const summary = data.summary;

    // Total Return
    const totalReturnPct = analytics.total_return_pct || 0;
    const totalReturnDollar = summary.net_portfolio_value - summary.total_invested;

    document.getElementById('total-return').textContent = totalReturnPct >= 0 ?
        `+${totalReturnPct.toFixed(2)}%` : `${totalReturnPct.toFixed(2)}%`;
    document.getElementById('total-return').className = totalReturnPct >= 0 ? 'hero-value positive' : 'hero-value negative';

    const deltaElem = document.getElementById('total-return-delta');
    deltaElem.textContent = totalReturnDollar >= 0 ?
        `▲ $${totalReturnDollar.toLocaleString()}` : `▼ $${Math.abs(totalReturnDollar).toLocaleString()}`;
    deltaElem.className = totalReturnDollar >= 0 ? 'delta positive' : 'delta negative';

    // Net Portfolio Value
    document.getElementById('net-portfolio-value').textContent = '$' + summary.net_portfolio_value.toLocaleString();

    // ROI
    const roi = summary.roi !== null ? summary.roi : 0;
    const roiElem = document.getElementById('roi');
    roiElem.textContent = roi !== null ? (roi >= 0 ? `+${roi.toFixed(2)}%` : `${roi.toFixed(2)}%`) : 'N/A';
    roiElem.className = roi >= 0 ? 'hero-value positive' : 'hero-value negative';

    // ==== INVESTMENT OVERVIEW ====
    document.getElementById('total-invested').textContent = '$' + summary.total_invested.toLocaleString();
    document.getElementById('current-value').textContent = '$' + summary.current_value.toLocaleString();
    document.getElementById('total-shares').textContent = summary.total_shares.toLocaleString();
    document.getElementById('average-cost').textContent = '$' + summary.average_cost.toLocaleString();
    document.getElementById('total-dividends').textContent = '$' + summary.total_dividends.toLocaleString();

    if (summary.account_balance !== null && summary.account_balance !== undefined) {
        document.getElementById('account-balance-summary').textContent = '$' + summary.account_balance.toLocaleString();
    } else {
        document.getElementById('account-balance-summary').textContent = '-';
    }

    // ==== ANALYTICS - RISK METRICS ====
    // Sharpe Ratio
    const sharpe = analytics.sharpe_ratio || 0;
    const sharpeElem = document.getElementById('sharpe-ratio');
    sharpeElem.textContent = sharpe.toFixed(2);

    let sharpeLabel = '';
    let sharpeClass = '';
    if (sharpe >= 3.0) {
        sharpeLabel = 'Excellent';
        sharpeClass = 'sharpe-excellent';
    } else if (sharpe >= 2.0) {
        sharpeLabel = 'Very Good';
        sharpeClass = 'sharpe-good';
    } else if (sharpe >= 1.0) {
        sharpeLabel = 'Good';
        sharpeClass = 'sharpe-fair';
    } else {
        sharpeLabel = 'Poor';
        sharpeClass = 'sharpe-poor';
    }
    sharpeElem.className = `analytics-value ${sharpeClass}`;
    document.getElementById('sharpe-label').textContent = sharpeLabel;

    // Max Drawdown
    const maxDD = analytics.max_drawdown || 0;
    const maxDDElem = document.getElementById('max-drawdown');
    maxDDElem.textContent = maxDD.toFixed(2) + '%';

    let ddClass = '';
    if (maxDD >= -10) {
        ddClass = 'drawdown-low';
    } else if (maxDD >= -20) {
        ddClass = 'drawdown-moderate';
    } else {
        ddClass = 'drawdown-high';
    }
    maxDDElem.className = `analytics-value ${ddClass}`;

    const peakDate = analytics.max_drawdown_peak_date;
    const troughDate = analytics.max_drawdown_trough_date;
    if (peakDate && troughDate) {
        document.getElementById('drawdown-dates').textContent = `${peakDate} → ${troughDate}`;
    } else {
        document.getElementById('drawdown-dates').textContent = '-';
    }

    // Volatility
    const vol = analytics.volatility || 0;
    document.getElementById('volatility').textContent = vol.toFixed(2) + '%';

    // Win Rate
    const winRate = analytics.win_rate || 0;
    document.getElementById('win-rate').textContent = winRate.toFixed(1) + '%';
    document.getElementById('win-rate-fill').style.width = winRate + '%';

    // ==== ANALYTICS - PERFORMANCE METRICS ====
    // CAGR
    const cagr = analytics.cagr || 0;
    const cagrElem = document.getElementById('cagr');
    cagrElem.textContent = cagr >= 0 ? `+${cagr.toFixed(2)}%` : `${cagr.toFixed(2)}%`;
    cagrElem.className = cagr >= 0 ? 'analytics-value positive' : 'analytics-value negative';

    // Best Day
    const bestDay = analytics.best_day || 0;
    const bestDayElem = document.getElementById('best-day');
    bestDayElem.textContent = `+${bestDay.toFixed(2)}%`;
    bestDayElem.className = 'analytics-value positive';
    document.getElementById('best-day-date').textContent = analytics.best_day_date || '-';

    // Worst Day
    const worstDay = analytics.worst_day || 0;
    const worstDayElem = document.getElementById('worst-day');
    worstDayElem.textContent = `${worstDay.toFixed(2)}%`;
    worstDayElem.className = 'analytics-value negative';
    document.getElementById('worst-day-date').textContent = analytics.worst_day_date || '-';

    // Calmar Ratio
    const calmar = analytics.calmar_ratio || 0;
    const calmarElem = document.getElementById('calmar-ratio');
    calmarElem.textContent = calmar.toFixed(2);

    let calmarLabel = '';
    let calmarClass = '';
    if (calmar >= 5.0) {
        calmarLabel = 'Excellent';
        calmarClass = 'calmar-excellent';
    } else if (calmar >= 3.0) {
        calmarLabel = 'Very Good';
        calmarClass = 'calmar-good';
    } else if (calmar >= 1.0) {
        calmarLabel = 'Good';
        calmarClass = 'calmar-fair';
    } else {
        calmarLabel = 'Poor';
        calmarClass = 'calmar-poor';
    }
    calmarElem.className = `analytics-value ${calmarClass}`;
    document.getElementById('calmar-label').textContent = calmarLabel;

    // ==== BENCHMARK SECTION ====
    const benchmarkSection = document.getElementById('benchmark-section');
    if (data.benchmark_summary) {
        benchmarkSection.style.display = 'block';
        document.getElementById('benchmark-value').textContent = '$' + data.benchmark_summary.current_value.toLocaleString();

        // Alpha
        const alpha = analytics.alpha || 0;
        const alphaElem = document.getElementById('alpha');
        alphaElem.textContent = alpha >= 0 ? `+${alpha.toFixed(2)}%` : `${alpha.toFixed(2)}%`;
        alphaElem.className = alpha >= 0 ? 'positive' : 'negative';
        document.getElementById('alpha-label').textContent = alpha >= 0 ? 'Outperforming' : 'Underperforming';

        // Beta
        const beta = analytics.beta || 1.0;
        document.getElementById('beta').textContent = beta.toFixed(2);
        let betaLabel = '';
        if (beta > 1.1) {
            betaLabel = 'Higher Volatility';
        } else if (beta < 0.9) {
            betaLabel = 'Lower Volatility';
        } else {
            betaLabel = 'Similar Volatility';
        }
        document.getElementById('beta-label').textContent = betaLabel;
    } else {
        benchmarkSection.style.display = 'none';
    }

    // ==== MARGIN SECTION ====
    const marginSection = document.getElementById('margin-section');
    const hasMargin = summary.total_borrowed > 0 || summary.margin_calls > 0;

    if (hasMargin) {
        marginSection.style.display = 'block';
        document.getElementById('total-borrowed').textContent = '$' + summary.total_borrowed.toLocaleString();
        document.getElementById('interest-paid').textContent = '$' + summary.total_interest_paid.toLocaleString();
        document.getElementById('current-leverage').textContent = summary.current_leverage.toFixed(2) + 'x';
        document.getElementById('margin-calls').textContent = summary.margin_calls.toString();

        // Handle No Margin Summary
        const noMarginCards = document.querySelectorAll('.no-margin-card');
        if (data.no_margin_summary) {
            document.getElementById('no-margin-value').textContent = '$' + data.no_margin_summary.current_value.toLocaleString();

            const noMarginROI = data.no_margin_summary.roi || 0;
            const roiElement = document.getElementById('no-margin-roi');
            roiElement.textContent = noMarginROI.toFixed(2) + '%';
            roiElement.className = noMarginROI >= 0 ? 'positive' : 'negative';

            noMarginCards.forEach(card => card.style.display = 'block');
        } else {
            noMarginCards.forEach(card => card.style.display = 'none');
        }
    } else {
        marginSection.style.display = 'none';
    }


    const ctx = document.getElementById('dcaChart').getContext('2d');

    if (chartInstance) {
        chartInstance.destroy();
    }

    const datasets = [
        {
            label: 'Portfolio Value',
            data: data.portfolio,
            borderColor: '#a78bfa', // Brighter purple
            backgroundColor: 'rgba(167, 139, 250, 0.1)',
            borderWidth: 3,
            pointRadius: 0,
            pointHoverRadius: 6,
            fill: true,
            tension: 0.4
        },
        {
            label: 'Net Portfolio Value (Equity)',
            data: data.net_portfolio,
            borderColor: '#06b6d4', // Cyan
            backgroundColor: 'rgba(6, 182, 212, 0.1)',
            borderWidth: 3,
            pointRadius: 0,
            pointHoverRadius: 6,
            fill: true,
            tension: 0.4
        },
        {
            label: 'Total Invested',
            data: data.invested,
            borderColor: '#cbd5e1', // Lighter gray
            borderDash: [5, 5],
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 6,
            fill: false,
            tension: 0.4,
            hidden: true // Hide by default to reduce clutter
        },
        {
            label: 'Cumulative Dividends',
            data: data.dividends,
            borderColor: '#4ade80', // Bright green
            backgroundColor: 'rgba(74, 222, 128, 0.1)',
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 6,
            fill: true,
            tension: 0.4,
            hidden: true // Hide by default
        }
    ];

    // Add Account Balance if available (check if any value is not null)
    if (data.balance && data.balance.some(val => val !== null)) {
        datasets.push({
            label: 'Account Balance',
            data: data.balance,
            borderColor: '#f472b6', // Pink
            borderDash: [2, 2],
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 6,
            fill: false,
            tension: 0.4
        });
    }

    // Add Margin data if available
    if (data.borrowed && data.borrowed.some(val => val > 0)) {
        datasets.push({
            label: 'Borrowed Amount',
            data: data.borrowed,
            borderColor: '#fb923c', // Orange
            backgroundColor: 'rgba(251, 146, 60, 0.1)',
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 6,
            fill: true,
            tension: 0.4,
            yAxisID: 'y'
        });
    }

    if (data.interest && data.interest.some(val => val > 0)) {
        datasets.push({
            label: 'Interest Paid',
            data: data.interest,
            borderColor: '#ef4444', // Red
            borderDash: [3, 3],
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 6,
            fill: false,
            tension: 0.4,
            yAxisID: 'y',
            hidden: true // Hide by default
        });
    }

    // Add leverage line on secondary axis
    let leverageMin = 1;
    let leverageMax = 2;
    if (data.leverage && data.leverage.some(val => val > 1.0)) {
        // Calculate dynamic min/max for leverage axis
        const leverageValues = data.leverage.filter(val => val > 0);
        leverageMin = Math.max(1, Math.min(...leverageValues) * 0.95); // 5% padding below, min 1.0
        leverageMax = Math.max(...leverageValues) * 1.05; // 5% padding above

        datasets.push({
            label: 'Leverage',
            data: data.leverage,
            borderColor: '#fbbf24', // Amber
            borderWidth: 1.5, // Thinner line
            borderDash: [10, 5],
            pointRadius: 0,
            pointHoverRadius: 6,
            fill: false,
            tension: 0.4,
            yAxisID: 'y1'  // Use secondary Y-axis
        });
    }

    // Add no-margin comparison when using margin
    if (data.no_margin && data.no_margin.length > 0) {
        datasets.push({
            label: `${ticker} (No Margin)`,
            data: data.no_margin,
            borderColor: '#a78bfa', // Purple
            borderWidth: 2,
            borderDash: [5, 3],
            pointRadius: 0,
            pointHoverRadius: 6,
            fill: false,
            tension: 0.4,
            yAxisID: 'y'
        });
    }

    if (data.benchmark && data.benchmark.length > 0) {
        datasets.push({
            label: `Benchmark (${benchmarkTicker || 'SPY'})`,
            data: data.benchmark,
            borderColor: '#9ca3af', // Gray
            borderDash: [2, 2],
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 6,
            fill: false,
            tension: 0.4
        });
    }

    if (data.average_cost && data.average_cost.length > 0) {
        datasets.push({
            label: 'Average Cost',
            data: data.average_cost,
            borderColor: '#f59e0b', // Amber/Orange
            borderDash: [5, 5],
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 6,
            fill: false,
            tension: 0.4,
            yAxisID: 'y'
        });
    }

    // Add withdrawal cumulative amount if available
    if (data.withdrawals && data.withdrawals.some(val => val > 0)) {
        datasets.push({
            label: 'Total Withdrawn',
            data: data.withdrawals,
            borderColor: '#10b981', // Green
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 6,
            fill: true,
            tension: 0.4,
            yAxisID: 'y'
        });
    }


    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.dates,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#94a3b8' }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    position: 'left',
                    grid: {
                        color: '#334155'
                    },
                    ticks: {
                        color: '#94a3b8'
                    }
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    min: leverageMin,
                    max: leverageMax,
                    grid: {
                        drawOnChartArea: false  // Don't draw grid lines for secondary axis
                    },
                    ticks: {
                        color: '#fbbf24',  // Amber color for leverage
                        callback: function (value) {
                            return value.toFixed(1) + 'x';
                        }
                    },
                    title: {
                        display: true,
                        text: 'Leverage',
                        color: '#fbbf24'
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#94a3b8'
                    }
                }
            }
        },
        plugins: [{
            id: 'marginCallMarkers',
            afterDraw: (chart) => {
                if (!data.margin_call_dates || data.margin_call_dates.length === 0) return;

                const ctx = chart.ctx;
                const xAxis = chart.scales.x;
                const yAxis = chart.scales.y;

                ctx.save();
                data.margin_call_dates.forEach(date => {
                    const dateIndex = data.dates.indexOf(date);
                    if (dateIndex === -1) return;

                    const x = xAxis.getPixelForValue(dateIndex);
                    const topY = yAxis.top;
                    const bottomY = yAxis.bottom;

                    // Draw vertical red line
                    ctx.strokeStyle = '#ef4444';
                    ctx.lineWidth = 2;
                    ctx.setLineDash([5, 5]);
                    ctx.beginPath();
                    ctx.moveTo(x, topY);
                    ctx.lineTo(x, bottomY);
                    ctx.stroke();
                    ctx.setLineDash([]);

                    // Draw "Margin Call" label
                    ctx.fillStyle = '#ef4444';
                    ctx.font = 'bold 10px sans-serif';
                    ctx.textAlign = 'center';
                    ctx.fillText('⚠ Margin Call', x, topY + 15);
                });
                ctx.restore();
            }
        },
        {
            id: 'withdrawalModeBackground',
            beforeDraw: (chart) => {
                if (!data.withdrawal_mode || !data.withdrawal_mode.some(val => val === true)) return;

                const ctx = chart.ctx;
                const xAxis = chart.scales.x;
                const yAxis = chart.scales.y;

                // Find first index where withdrawal mode is active
                const startIndex = data.withdrawal_mode.findIndex(val => val === true);
                if (startIndex === -1) return;

                const startX = xAxis.getPixelForValue(startIndex);
                const endX = xAxis.right;

                // Draw green tinted background for withdrawal period
                ctx.save();
                ctx.fillStyle = 'rgba(16, 185, 129, 0.05)'; // Light green tint
                ctx.fillRect(startX, yAxis.top, endX - startX, yAxis.bottom - yAxis.top);
                ctx.restore();
            }
        },
        {
            id: 'withdrawalMarkers',
            afterDraw: (chart) => {
                if (!data.withdrawal_dates || data.withdrawal_dates.length === 0) return;

                const ctx = chart.ctx;
                const xAxis = chart.scales.x;
                const yAxis = chart.scales.y;

                ctx.save();
                data.withdrawal_dates.forEach(date => {
                    const dateIndex = data.dates.indexOf(date);
                    if (dateIndex === -1) return;

                    const x = xAxis.getPixelForValue(dateIndex);
                    const topY = yAxis.top;

                    // Draw small green dot at top
                    ctx.fillStyle = '#10b981';
                    ctx.beginPath();
                    ctx.arc(x, topY + 25, 4, 0, Math.PI * 2);
                    ctx.fill();
                });
                ctx.restore();
            }
        }]
    });

    // ==== POPULATE MARGIN CALL TABLE ====
    const marginCallTableContainer = document.getElementById('margin-call-table-container');
    const marginCallTableBody = document.getElementById('margin-call-table-body');

    if (data.margin_call_details && data.margin_call_details.length > 0) {
        // Clear existing rows
        marginCallTableBody.innerHTML = '';

        // Add row for each margin call
        data.margin_call_details.forEach((call, index) => {
            const row = document.createElement('tr');

            // Helper function to format equity ratio with color
            const formatEquityRatio = (ratio, isAfter = false, portfolioValue = null) => {
                // Check if this is a complete liquidation (portfolio = 0 after)
                if (isAfter && portfolioValue !== null && portfolioValue === 0) {
                    return `<span class="equity-ratio-warning">Complete Liquidation</span>`;
                }

                const percentage = (ratio * 100).toFixed(2) + '%';
                let className = '';
                if (ratio < 0.25) {
                    className = 'equity-ratio-danger';
                } else if (ratio < 0.35) {
                    className = 'equity-ratio-warning';
                } else {
                    className = 'equity-ratio-safe';
                }
                return `<span class="${className}">${percentage}</span>`;
            };

            // Helper function to format currency
            const formatCurrency = (value) => {
                return '$' + value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
            };

            // Helper function to format number
            const formatNumber = (value) => {
                return value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
            };

            row.innerHTML = `
                <td><strong>${call.date}</strong></td>
                <td>${formatCurrency(call.price)}</td>
                <td>${formatEquityRatio(call.equity_ratio_before, false)}</td>
                <td>${formatEquityRatio(call.equity_ratio_after, true, call.portfolio_value_after)}</td>
                <td>${formatNumber(call.shares_sold)}</td>
                <td>${formatCurrency(call.sale_proceeds)}</td>
                <td>${formatCurrency(call.debt_paid)}</td>
                <td>${formatCurrency(call.portfolio_value_before)}</td>
                <td>${formatCurrency(call.portfolio_value_after)}</td>
                <td>${formatCurrency(call.equity_before)}</td>
                <td>${formatCurrency(call.equity_after)}</td>
            `;

            marginCallTableBody.appendChild(row);
        });

        // Show the table
        marginCallTableContainer.style.display = 'block';
    } else {
        // Hide the table if no margin calls
        marginCallTableContainer.style.display = 'none';
    }

    // ==== POPULATE WITHDRAWAL SECTION ====
    const withdrawalSection = document.getElementById('withdrawal-section');

    if (summary && summary.total_withdrawn > 0) {
        // Show withdrawal section
        withdrawalSection.style.display = 'block';

        // Populate summary cards
        document.getElementById('total-withdrawn').textContent =
            '$' + summary.total_withdrawn.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});

        document.getElementById('withdrawal-start-date').textContent =
            summary.withdrawal_mode_start_date || 'N/A';

        document.getElementById('withdrawal-count').textContent =
            (data.withdrawal_dates ? data.withdrawal_dates.length : 0).toString();

        const status = summary.withdrawal_mode_active ?
            '<span style="color: #10b981;">Active</span>' :
            '<span style="color: #94a3b8;">Completed</span>';
        document.getElementById('withdrawal-status').innerHTML = status;
    } else {
        withdrawalSection.style.display = 'none';
    }

    // ==== POPULATE WITHDRAWAL TABLE ====
    const withdrawalTableContainer = document.getElementById('withdrawal-table-container');
    const withdrawalTableBody = document.getElementById('withdrawal-table-body');

    if (data.withdrawal_details && data.withdrawal_details.length > 0) {
        withdrawalTableBody.innerHTML = '';

        data.withdrawal_details.forEach((withdrawal) => {
            const row = document.createElement('tr');

            const formatCurrency = (value) => {
                return '$' + value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
            };

            const formatNumber = (value) => {
                return value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
            };

            // Check event type
            const eventType = withdrawal.event_type;

            if (eventType === 'dividend') {
                // Dividend income row (green tint)
                row.style.backgroundColor = 'rgba(34, 197, 94, 0.1)'; // Green tint
                row.style.borderLeft = '4px solid #22c55e'; // Green border
                const cashIncrease = (withdrawal.cash_after || 0) - (withdrawal.cash_before || 0);
                row.innerHTML = `
                    <td><strong>${withdrawal.date}</strong><br><span style="color: #22c55e; font-size: 0.85em;">💰 Dividend Income</span></td>
                    <td colspan="3" style="color: #22c55e;">
                        <strong>+${formatCurrency(withdrawal.dividend_income)}</strong> dividend
                        <br><span style="font-size: 0.85em;">${formatCurrency(withdrawal.dividend_per_share)}/share × ${formatNumber(withdrawal.shares_owned)} shares</span>
                    </td>
                    <td>—</td>
                    <td style="color: #22c55e;">
                        Cash: ${formatCurrency(withdrawal.cash_before)} → ${formatCurrency(withdrawal.cash_after)}
                        <br><span style="font-size: 0.85em; color: #22c55e;">+${formatCurrency(cashIncrease)}</span>
                    </td>
                    <td>${formatCurrency(withdrawal.cumulative_withdrawn)}</td>
                `;
            } else if (eventType === 'threshold_debt_payoff') {
                // Debt payoff row (orange tint)
                row.style.backgroundColor = 'rgba(251, 146, 60, 0.15)';
                row.style.borderLeft = '4px solid #fb923c';
                row.innerHTML = `
                    <td><strong>${withdrawal.date}</strong><br><span style="color: #fb923c; font-size: 0.85em;">⚡ Threshold Reached - Debt Payoff</span></td>
                    <td>${formatCurrency(withdrawal.price)}</td>
                    <td>${formatNumber(withdrawal.shares_sold)}</td>
                    <td>${formatCurrency(withdrawal.sale_proceeds)}</td>
                    <td style="color: #fb923c;"><strong>${formatCurrency(withdrawal.debt_repaid)}</strong></td>
                    <td class="withdrawal-amount">$0.00</td>
                    <td><strong>${formatCurrency(withdrawal.cumulative_withdrawn)}</strong></td>
                `;
            } else {
                // Regular withdrawal row
                const fundedBy = withdrawal.funded_by || '';
                let fundingBadge = '';
                if (fundedBy === 'dividends') {
                    fundingBadge = '<br><span style="color: #22c55e; font-size: 0.85em;">✓ Funded by Dividends</span>';
                } else if (fundedBy === 'share_sale') {
                    fundingBadge = '<br><span style="color: #8b5cf6; font-size: 0.85em;">📊 Shares Sold</span>';
                }

                row.innerHTML = `
                    <td><strong>${withdrawal.date}</strong>${fundingBadge}</td>
                    <td>${withdrawal.price ? formatCurrency(withdrawal.price) : '—'}</td>
                    <td>${formatNumber(withdrawal.shares_sold || 0)}</td>
                    <td>${formatCurrency(withdrawal.sale_proceeds || 0)}</td>
                    <td>${formatCurrency(withdrawal.debt_repaid || 0)}</td>
                    <td class="withdrawal-amount">${formatCurrency(withdrawal.amount_withdrawn || 0)}</td>
                    <td><strong>${formatCurrency(withdrawal.cumulative_withdrawn)}</strong></td>
                `;
            }

            withdrawalTableBody.appendChild(row);
        });

        withdrawalTableContainer.style.display = 'block';
    } else {
        withdrawalTableContainer.style.display = 'none';
    }
}

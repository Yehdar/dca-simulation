# Biweekly ETF Investor

A dark-mode Python/Tkinter desktop application for historical Canadian ETF backtesting using real Yahoo Finance data. It compares VFV, VDY, QQC, and saved custom portfolios across consistent contribution periods.

## Features

- Portfolio Growth tab with biweekly DCA, initial investment, common-period mode, contribution/growth charts, and three dividend modes: DRIP (`Adj Close` without manual dividend additions), cash distributions tracked separately using `Close`, or price-only `Close`.
- Rolling Returns tab for 1, 2, 3, 5, 10, 15, and 20-year windows, with annualized-return charts, histograms, box plots, and summary statistics.
- Risk Analysis tab with cash-flow-adjusted maximum drawdown, drawdown dates, recovery status, annualized volatility, calendar-year extremes, Sharpe ratio, and risk/return scatter plot.
- Portfolio Builder with editable allocations, predefined templates, saved JSON configurations, and no/new-contribution/quarterly/annual rebalancing.
- Sortable Performance Comparison table and CSV export containing XIRR, time-weighted return, simple return, growth, cash dividends, drawdown, volatility, and Sharpe ratio.
- Local CSV caching in `.market_cache/`; contribution amount, dividend mode, and portfolio changes reuse cached data without another API request.
- Background downloads and calculations keep Tkinter responsive.

## Install and run

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Tkinter is included with most Python installations. Some Linux distributions provide it separately as `python3-tk`.

## Tests

The deterministic calculation tests use synthetic data only; the application itself never mocks historical market data.

```bash
python -m unittest discover -s tests -v
```

## Important interpretation notes

Common-period mode is enabled by default. It uses the latest required start date, the earliest common end date, and one shared contribution schedule. If the requested period exceeds the overlapping history, the status bar reports the shortened period. Turning it off allows each investment to use its own history, but absolute values are then not directly comparable.

Rolling windows overlap, so they are not independent observations. A percentage of profitable historical windows is descriptive of this sample, not a guaranteed future probability. Historical performance does not guarantee future returns.

The simulations assume fractional shares, zero commissions, zero taxes, and no slippage. Rebalancing is likewise modeled without transaction costs or tax consequences. Yahoo Finance data can be delayed, revised, or temporarily unavailable; this tool is educational and is not financial advice.

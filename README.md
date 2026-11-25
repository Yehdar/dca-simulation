# Biweekly ETF Investor

A lightweight Python/Tkinter desktop application that uses real historical data from Yahoo Finance to visualize investing in Canadian-listed ETFs every 14 calendar days.

## Features

- VFV, VDY, and QQC scenarios, independently funded per ETF.
- Fractional shares, optional initial lump sum, dividend reinvestment, and an optional common start date.
- Cached historical CSV data in `.market_cache/` to reduce repeat downloads.
- Background data fetching so the UI stays responsive.
- Portfolio and contribution/growth charts with hover details.
- XIRR money-weighted return, contribution count, duration, dividend cash tracking, and CSV summary export.

## Install and run

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Tkinter is included with most Python installations. On some Linux distributions it is provided by a separate system package such as `python3-tk`.

## Notes on the model

Each selected ETF receives the full biweekly amount; the amount is not split between ETFs. Scheduled investments happen every 14 calendar days and are moved forward to the next available trading day. If a selected start year predates an ETF's available history, that ETF begins at its earliest downloaded trading day and the UI shows that period in its card. The common start date option instead starts every selected ETF on the latest of their available starting dates.

With dividend reinvestment enabled, adjusted close is used to model total returns. With it disabled, close prices are used and distributions are accumulated as cash. The app assumes no taxes or commissions and does not fabricate or extrapolate prices before inception.

Historical performance does not guarantee future returns. Yahoo Finance data can be delayed, revised, or temporarily unavailable, so use this as an educational visualization rather than financial advice.

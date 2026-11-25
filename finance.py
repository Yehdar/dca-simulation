"""Data access and deterministic financial calculations for the ETF backtester."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd
import yfinance as yf

ETF_OPTIONS = {
    "VFV": {"ticker": "VFV.TO", "name": "Vanguard S&P 500 Index ETF", "color": "#5ea7ff"},
    "VDY": {"ticker": "VDY.TO", "name": "Vanguard FTSE Canadian High Dividend Yield Index ETF", "color": "#55d6a4"},
    "QQC": {"ticker": "QQC.TO", "name": "Invesco NASDAQ 100 Index ETF", "color": "#bd8cff"},
}
DIVIDEND_MODES = {
    "Reinvest dividends (DRIP)": "drip",
    "Collect dividends as cash": "cash",
    "Exclude dividends (price only)": "price",
}
REBALANCING = ("No rebalancing", "Rebalance through new contributions", "Quarterly rebalancing", "Annual rebalancing")
PORTFOLIO_TEMPLATES = {
    "100% VFV": {"VFV": 1.0, "VDY": 0.0, "QQC": 0.0},
    "100% VDY": {"VFV": 0.0, "VDY": 1.0, "QQC": 0.0},
    "100% QQC": {"VFV": 0.0, "VDY": 0.0, "QQC": 1.0},
    "Equal Weight": {"VFV": 0.3334, "VDY": 0.3333, "QQC": 0.3333},
    "Growth Focused": {"VFV": 0.5, "VDY": 0.0, "QQC": 0.5},
    "Dividend Focused": {"VFV": 0.3, "VDY": 0.6, "QQC": 0.1},
    "Balanced": {"VFV": 0.5, "VDY": 0.3, "QQC": 0.2},
}


def xirr(cash_flows: list[tuple[pd.Timestamp, float]]) -> Optional[float]:
    if not cash_flows or not any(v < 0 for _, v in cash_flows) or not any(v > 0 for _, v in cash_flows):
        return None
    first = cash_flows[0][0]

    def npv(rate: float) -> float:
        return sum(value / (1 + rate) ** ((when - first).days / 365.0) for when, value in cash_flows)

    low, high = -0.9999, 1.0
    while npv(low) * npv(high) > 0 and high < 1_000_000:
        high *= 2
    if npv(low) * npv(high) > 0:
        return None
    for _ in range(100):
        middle = (low + high) / 2
        if abs(npv(middle)) < 1e-8:
            return middle
        if npv(low) * npv(middle) <= 0:
            high = middle
        else:
            low = middle
    return (low + high) / 2


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame.index = pd.to_datetime(frame.index)
    if getattr(frame.index, "tz", None) is not None:
        frame.index = frame.index.tz_localize(None)
    for column in ("Close", "Adj Close", "Dividends"):
        if column not in frame.columns:
            frame[column] = 0.0
    return frame[["Close", "Adj Close", "Dividends"]].apply(pd.to_numeric, errors="coerce").dropna(subset=["Close", "Adj Close"]).sort_index()


class MarketData:
    def __init__(self, cache_dir: Path, status: Optional[Callable[[str], None]] = None):
        self.cache_dir = cache_dir
        self.status = status or (lambda _: None)
        self.cache_dir.mkdir(exist_ok=True)

    def load(self, symbol: str, end: date | pd.Timestamp) -> pd.DataFrame:
        config = ETF_OPTIONS[symbol]
        cache_file = self.cache_dir / f"{config['ticker'].replace('.', '_')}.csv"
        frame = None
        if cache_file.exists():
            try:
                frame = normalize_frame(pd.read_csv(cache_file, parse_dates=["Date"], index_col="Date"))
            except (OSError, ValueError, KeyError):
                frame = None
        end_ts = pd.Timestamp(end).normalize()
        fresh = cache_file.exists() and (datetime.now().timestamp() - cache_file.stat().st_mtime) < 86_400
        if frame is None or not fresh or frame.empty or frame.index.max() < end_ts - pd.Timedelta(days=5):
            self.status(f"Downloading {symbol} history…")
            remote = yf.Ticker(config["ticker"]).history(start="1990-01-01", end=(end_ts + pd.Timedelta(days=1)).strftime("%Y-%m-%d"), auto_adjust=False, actions=True)
            if remote.empty:
                raise ValueError(f"No historical data returned for {symbol} ({config['ticker']}).")
            frame = normalize_frame(remote)
            frame.to_csv(cache_file, index_label="Date")
        return frame.loc[frame.index <= end_ts].copy()


@dataclass
class Simulation:
    name: str
    symbols: tuple[str, ...]
    start: pd.Timestamp
    end: pd.Timestamp
    dates: pd.DatetimeIndex
    contributions: pd.Series
    values: pd.Series
    cash: pd.Series
    shares: dict[str, pd.Series]
    total_contributed: float
    final_value: float
    cash_received: float
    growth: float
    return_pct: float
    xirr: Optional[float]
    time_weighted_return: Optional[float]
    contribution_count: int
    risk: dict = field(default_factory=dict)

    @property
    def duration_years(self) -> float:
        return max(0, (self.end - self.start).days) / 365.25

    @property
    def duration_text(self) -> str:
        total_months = int(round((self.end - self.start).days / 30.4375))
        return f"{total_months // 12}y {total_months % 12}m"


def trading_schedule(index: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp, frequency_days: int = 14) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(index)
    if len(index) == 0:
        return index
    dates: list[pd.Timestamp] = []
    scheduled = pd.Timestamp(start)
    while scheduled <= end:
        positions = index.searchsorted(scheduled, side="left")
        if positions < len(index):
            date_value = index[positions]
            if not dates or date_value != dates[-1]:
                dates.append(date_value)
        scheduled += pd.Timedelta(days=frequency_days)
    return pd.DatetimeIndex(dates)


def _single_simulation(name: str, symbol: str, data: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, amount: float, initial: float, mode: str, schedule: Optional[pd.DatetimeIndex] = None) -> Simulation:
    frame = normalize_frame(data).loc[start:end]
    if frame.empty:
        raise ValueError(f"{symbol} does not have complete data for this period.")
    index = frame.index
    schedule = schedule if schedule is not None else trading_schedule(index, index[0], index[-1])
    price_column = "Adj Close" if mode == "drip" else "Close"
    shares = 0.0
    cash = 0.0
    contributions = pd.Series(0.0, index=index)
    values = pd.Series(0.0, index=index)
    cash_series = pd.Series(0.0, index=index)
    share_series = pd.Series(0.0, index=index)
    schedule_set = set(schedule)
    for current in index:
        if mode == "cash" and shares:
            cash += float(frame.at[current, "Dividends"] or 0.0) * shares
        if current in schedule_set:
            invested = amount + (initial if current == index[0] else 0.0)
            shares += invested / float(frame.at[current, price_column])
            contributions.at[current] += invested
        values.at[current] = shares * float(frame.at[current, price_column])
        cash_series.at[current] = cash
        share_series.at[current] = shares
    total = float(contributions.sum())
    final = float(values.iloc[-1])
    combined = final + cash
    flows = [(-float(value), when) for when, value in contributions.items() if value > 0]
    flows = [(when, value) for value, when in flows] + [(index[-1], combined)]
    return Simulation(name, (symbol,), index[0], index[-1], index, contributions.cumsum(), values, cash_series, {symbol: share_series}, total, final, cash, combined - total, (combined - total) / total * 100 if total else 0, xirr(flows), None, int((contributions > 0).sum()))


def simulate_single(symbol: str, data: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, amount: float, initial: float, mode: str, schedule: Optional[pd.DatetimeIndex] = None, name: Optional[str] = None) -> Simulation:
    return _single_simulation(name or symbol, symbol, data, start, end, amount, initial, mode, schedule)


def simulate_portfolio(name: str, allocations: dict[str, float], frames: dict[str, pd.DataFrame], start: pd.Timestamp, end: pd.Timestamp, amount: float, initial: float, mode: str, rebalance: str = "No rebalancing", schedule: Optional[pd.DatetimeIndex] = None) -> Simulation:
    symbols = tuple(symbol for symbol, weight in allocations.items() if weight > 0)
    common_index = pd.DatetimeIndex(sorted(set.intersection(*(set(normalize_frame(frames[symbol]).loc[start:end].index) for symbol in symbols))))
    if common_index.empty:
        raise ValueError(f"{name} has no common historical data for this period.")
    start_actual, end_actual = common_index[0], common_index[-1]
    schedule = schedule if schedule is not None else trading_schedule(common_index, start_actual, end_actual)
    prices = {symbol: normalize_frame(frames[symbol]).reindex(common_index)["Adj Close" if mode == "drip" else "Close"].ffill() for symbol in symbols}
    dividends = {symbol: normalize_frame(frames[symbol]).reindex(common_index)["Dividends"].fillna(0) for symbol in symbols}
    holdings = {symbol: 0.0 for symbol in symbols}
    cash = 0.0
    contribution_series = pd.Series(0.0, index=common_index)
    values = pd.Series(0.0, index=common_index)
    cash_series = pd.Series(0.0, index=common_index)
    shares_series = {symbol: pd.Series(0.0, index=common_index) for symbol in symbols}
    schedule_set = set(schedule)
    last_rebalance: Optional[pd.Timestamp] = None
    for current in common_index:
        if mode == "cash":
            cash += sum(dividends[symbol].at[current] * holdings[symbol] for symbol in symbols)
        current_value = sum(holdings[symbol] * prices[symbol].at[current] for symbol in symbols)
        contribution = 0.0
        if current in schedule_set:
            contribution = amount + (initial if current == start_actual else 0.0)
            targets = {symbol: contribution * allocations[symbol] for symbol in symbols}
            if rebalance == "Rebalance through new contributions" and current_value > 0:
                portfolio_after = current_value + contribution
                deficits = {symbol: max(0.0, portfolio_after * allocations[symbol] - holdings[symbol] * prices[symbol].at[current]) for symbol in symbols}
                deficit_total = sum(deficits.values())
                targets = {symbol: (deficits[symbol] / deficit_total * contribution if deficit_total else contribution * allocations[symbol]) for symbol in symbols}
            for symbol in symbols:
                holdings[symbol] += targets[symbol] / prices[symbol].at[current]
        interval = 3 if rebalance == "Quarterly rebalancing" else 12 if rebalance == "Annual rebalancing" else 0
        if interval and last_rebalance is not None and (current.year - last_rebalance.year) * 12 + current.month - last_rebalance.month >= interval:
            current_value = sum(holdings[symbol] * prices[symbol].at[current] for symbol in symbols)
            for symbol in symbols:
                holdings[symbol] = current_value * allocations[symbol] / prices[symbol].at[current]
            last_rebalance = current
        elif interval and current in schedule_set:
            last_rebalance = current
        contribution_series.at[current] = contribution
        values.at[current] = sum(holdings[symbol] * prices[symbol].at[current] for symbol in symbols)
        cash_series.at[current] = cash
        for symbol in symbols:
            shares_series[symbol].at[current] = holdings[symbol]
    total = float(contribution_series.sum())
    final = float(values.iloc[-1])
    combined = final + cash
    flows = [(when, -float(value)) for when, value in contribution_series.items() if value > 0] + [(end_actual, combined)]
    return Simulation(name, symbols, start_actual, end_actual, common_index, contribution_series.cumsum(), values, cash_series, shares_series, total, final, cash, combined - total, (combined - total) / total * 100 if total else 0, xirr(flows), None, int((contribution_series > 0).sum()))


def time_weighted_returns(simulation: Simulation) -> tuple[pd.Series, Optional[float]]:
    wealth = pd.Series(1.0, index=simulation.dates)
    previous_value = 0.0
    for current in simulation.dates:
        contribution = simulation.contributions.diff().fillna(simulation.contributions).at[current]
        denominator = previous_value + contribution
        factor = simulation.values.at[current] / denominator if denominator > 0 else 1.0
        wealth.at[current] = wealth.iloc[wealth.index.get_loc(current) - 1] * factor if wealth.index.get_loc(current) else factor
        previous_value = simulation.values.at[current]
    return wealth - 1, float(wealth.iloc[-1] - 1) if len(wealth) else None


def risk_metrics(simulation: Simulation, risk_free_rate: float = 0.02) -> dict:
    wealth_returns, twr = time_weighted_returns(simulation)
    wealth = wealth_returns + 1
    peaks = wealth.cummax()
    drawdown = wealth / peaks - 1
    bottom = drawdown.idxmin()
    peak_date = wealth.loc[:bottom].idxmax()
    max_dd = float(drawdown.loc[bottom])
    recovery_candidates = wealth.loc[bottom:][wealth.loc[bottom:] >= wealth.loc[peak_date]]
    recovery = recovery_candidates.index[0] if not recovery_candidates.empty else None
    daily_returns = wealth.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    volatility = float(daily_returns.std(ddof=1) * math.sqrt(252)) if len(daily_returns) > 1 else 0.0
    annual = wealth.resample("YE").last().pct_change().dropna()
    sharpe = ((float(daily_returns.mean()) * 252) - risk_free_rate) / volatility if volatility else None
    simulation.risk = {"drawdown_series": drawdown, "max_drawdown": max_dd, "drawdown_start": peak_date, "drawdown_bottom": bottom, "recovery": recovery, "recovery_text": "Not Yet Recovered" if recovery is None else str(recovery.date()), "recovery_days": None if recovery is None else (recovery - bottom).days, "volatility": volatility, "best_year": None if annual.empty else float(annual.max()), "worst_year": None if annual.empty else float(annual.min()), "sharpe": sharpe, "time_weighted_return": twr}
    simulation.time_weighted_return = twr
    return simulation.risk


def rolling_returns(symbol: str, data: pd.DataFrame, years: int, amount: float, mode: str, common_start: Optional[pd.Timestamp] = None, common_end: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    frame = normalize_frame(data)
    eligible = frame.index[(frame.index >= (common_start or frame.index[0])) & (frame.index + pd.DateOffset(years=years) <= (common_end or frame.index[-1]))]
    rows = []
    for start in eligible:
        target_end = frame.index[frame.index.searchsorted(start + pd.DateOffset(years=years), side="right") - 1]
        simulation = simulate_single(symbol, frame, start, target_end, amount, 0, mode)
        rows.append({"symbol": symbol, "start": start, "end": target_end, "return": simulation.xirr, "final_value": simulation.final_value, "profitable": simulation.growth > 0})
    return pd.DataFrame(rows)


def portfolio_allocations_valid(allocations: dict[str, float]) -> bool:
    return all(0 <= value <= 1 for value in allocations.values()) and abs(sum(allocations.values()) - 1.0) < 0.00005


def load_portfolios(path: Path) -> dict[str, dict[str, float]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {str(name): {symbol: float(values.get(symbol, 0)) for symbol in ETF_OPTIONS} for name, values in payload.items()}
    except (OSError, ValueError, TypeError):
        return {}


def save_portfolios(path: Path, portfolios: dict[str, dict[str, float]]) -> None:
    path.write_text(json.dumps(portfolios, indent=2), encoding="utf-8")

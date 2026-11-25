"""Biweekly ETF investing visualizer.

Run with: python main.py

The application deliberately keeps data retrieval, simulation, and rendering
separate so new tickers can be added to ETF_OPTIONS without changing the model.
"""

from __future__ import annotations

import csv
import math
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import tkinter as tk
import yfinance as yf
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import FuncFormatter
from tkinter import filedialog, messagebox, ttk


ETF_OPTIONS = {
    "VFV": {"ticker": "VFV.TO", "name": "Vanguard S&P 500 Index ETF", "color": "#5ea7ff"},
    "VDY": {"ticker": "VDY.TO", "name": "Vanguard FTSE Canadian High Dividend Yield Index ETF", "color": "#55d6a4"},
    "QQC": {"ticker": "QQC.TO", "name": "Invesco NASDAQ 100 Index ETF", "color": "#bd8cff"},
}
CACHE_DIR = Path(__file__).with_name(".market_cache")
BG = "#17191d"
PANEL = "#20242a"
TEXT = "#eef1f5"
MUTED = "#9aa4b2"
GRID = "#343a43"


@dataclass
class Simulation:
    symbol: str
    ticker: str
    start: pd.Timestamp
    end: pd.Timestamp
    dates: pd.DatetimeIndex
    contributions: pd.Series
    values: pd.Series
    cash_distributions: pd.Series
    total_contributed: float
    final_value: float
    cash_received: float
    growth: float
    return_pct: float
    xirr: Optional[float]
    contribution_count: int

    @property
    def duration(self) -> str:
        days = max(0, (self.end.date() - self.start.date()).days)
        years, remainder = divmod(days, 365)
        months = remainder // 30
        return f"{years}y {months}m"


def latest_weekday() -> date:
    current = date.today()
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def money(value: float) -> str:
    return f"${value:,.2f}"


def xirr(cash_flows: list[tuple[pd.Timestamp, float]]) -> Optional[float]:
    """Solve annualized money-weighted return using a bounded bisection search."""
    if not cash_flows or not any(v < 0 for _, v in cash_flows) or not any(v > 0 for _, v in cash_flows):
        return None
    first = cash_flows[0][0]

    def npv(rate: float) -> float:
        return sum(value / (1.0 + rate) ** (((when - first).days) / 365.0) for when, value in cash_flows)

    low, high = -0.9999, 1.0
    while npv(low) * npv(high) > 0 and high < 1_000_000:
        high *= 2
    if npv(low) * npv(high) > 0:
        return None
    for _ in range(120):
        middle = (low + high) / 2
        if abs(npv(middle)) < 1e-7:
            return middle
        if npv(low) * npv(middle) <= 0:
            high = middle
        else:
            low = middle
    return (low + high) / 2


class MarketData:
    def __init__(self, status: Callable[[str], None]):
        self.status = status
        CACHE_DIR.mkdir(exist_ok=True)

    def load(self, symbol: str, end: date) -> pd.DataFrame:
        config = ETF_OPTIONS[symbol]
        cache_file = CACHE_DIR / f"{config['ticker'].replace('.', '_')}.csv"
        frame: Optional[pd.DataFrame] = None
        if cache_file.exists():
            try:
                frame = pd.read_csv(cache_file, parse_dates=["Date"], index_col="Date")
            except (OSError, ValueError):
                frame = None
        cache_is_fresh = cache_file.exists() and (datetime.now().timestamp() - cache_file.stat().st_mtime) < 86_400
        requested_end = pd.Timestamp(end) + pd.Timedelta(days=1)
        if frame is None or not cache_is_fresh or frame.index.max() < requested_end - pd.Timedelta(days=5):
            self.status(f"Downloading {symbol} historical data…")
            remote = yf.Ticker(config["ticker"]).history(start="1990-01-01", end=requested_end.strftime("%Y-%m-%d"), auto_adjust=False, actions=True)
            if remote.empty:
                raise ValueError(f"No historical data was returned for {symbol} ({config['ticker']}).")
            frame = remote.reset_index()
            date_col = "Date" if "Date" in frame.columns else frame.columns[0]
            frame[date_col] = pd.to_datetime(frame[date_col]).dt.tz_localize(None)
            frame = frame.rename(columns={date_col: "Date"}).set_index("Date")
            for column in ("Close", "Adj Close", "Dividends"):
                if column not in frame:
                    frame[column] = 0.0
            frame[["Close", "Adj Close", "Dividends"]].to_csv(cache_file, index_label="Date")
        frame.index = pd.to_datetime(frame.index).tz_localize(None)
        return frame.loc[frame.index <= pd.Timestamp(end), ["Close", "Adj Close", "Dividends"]].sort_index().dropna(subset=["Close", "Adj Close"])


def simulate(symbol: str, data: pd.DataFrame, start_year: int, end_date: date, amount: float, initial: float, reinvest: bool, forced_start: Optional[pd.Timestamp] = None) -> Simulation:
    if data.empty:
        raise ValueError(f"{symbol} has no data through {end_date:%Y-%m-%d}.")
    requested_start = pd.Timestamp(forced_start or date(start_year, 1, 1))
    available = data.loc[data.index >= requested_start]
    if available.empty:
        available = data
    start = available.index[0]
    end = data.index[-1]
    index = data.loc[start:end].index
    prices = data["Adj Close"] if reinvest else data["Close"]
    shares = 0.0
    cash = 0.0
    contribution = pd.Series(0.0, index=index)
    values = pd.Series(0.0, index=index)
    cash_series = pd.Series(0.0, index=index)
    contribution_dates: list[pd.Timestamp] = []
    scheduled = start
    while scheduled <= end:
        candidate = index[index >= scheduled]
        if len(candidate):
            contribution_dates.append(candidate[0])
        scheduled += pd.Timedelta(days=14)
    if initial > 0:
        contribution_dates.insert(0, start)
    for current in index:
        if not reinvest:
            dividend = float(data.at[current, "Dividends"] or 0)
            if math.isnan(dividend):
                dividend = 0.0
            cash += dividend * shares
        if current in contribution_dates:
            invested = amount + (initial if current == start else 0.0)
            shares += invested / float(prices.at[current])
            contribution.at[current] += invested
        values.at[current] = shares * float(prices.at[current])
        cash_series.at[current] = cash
    total = float(contribution.sum())
    final = float(values.iloc[-1])
    growth = final + cash - total
    flows = [(when, -float(contribution.at[when])) for when in contribution.index if contribution.at[when] > 0]
    flows.append((end, final + cash))
    return Simulation(symbol, ETF_OPTIONS[symbol]["ticker"], start, end, index, contribution.cumsum(), values, cash_series, total, final, cash, growth, (growth / total * 100) if total else 0.0, xirr(flows), int((contribution > 0).sum()))


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Biweekly ETF Investor")
        self.geometry("1320x900")
        self.minsize(980, 700)
        self.configure(bg=BG)
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=BG)
        self.style.configure("Panel.TFrame", background=PANEL)
        self.style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        self.style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        self.style.configure("Panel.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 20))
        self.style.configure("TButton", background="#4d8edc", foreground="white", padding=(14, 8), borderwidth=0, font=("Segoe UI Semibold", 10))
        self.style.map("TButton", background=[("active", "#6da7ed")])
        self.style.configure("TEntry", fieldbackground="#2a2f37", foreground=TEXT, insertcolor=TEXT, borderwidth=0, padding=7)
        self.style.configure("TCombobox", fieldbackground="#2a2f37", foreground=TEXT, arrowcolor=TEXT, padding=6)
        self.style.configure("TCheckbutton", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        self.style.configure("Horizontal.TProgressbar", troughcolor="#2a2f37", background="#5ea7ff")
        self.selected = {symbol: tk.BooleanVar(value=True) for symbol in ETF_OPTIONS}
        self.start_year = tk.IntVar(value=max(2015, date.today().year - 10))
        self.amount = tk.StringVar(value="500")
        self.initial = tk.StringVar(value="0")
        self.end_date = tk.StringVar(value=latest_weekday().isoformat())
        self.reinvest = tk.BooleanVar(value=True)
        self.common_start = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready — select your assumptions and calculate.")
        self.progress = ttk.Progressbar(self, mode="indeterminate", style="Horizontal.TProgressbar")
        self.results: dict[str, Simulation] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=22)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Biweekly ETF Investor", style="Header.TLabel").pack(anchor="w")
        ttk.Label(outer, text="See what consistency could have done with real Canadian market history.", style="Muted.TLabel").pack(anchor="w", pady=(2, 14))
        controls = ttk.Frame(outer, style="Panel.TFrame", padding=16)
        controls.pack(fill="x", pady=(0, 14))
        fields = [("Start year", ttk.Combobox(controls, textvariable=self.start_year, values=list(range(1990, date.today().year + 1)), state="readonly", width=9)), ("Biweekly CAD", ttk.Entry(controls, textvariable=self.amount, width=12)), ("Initial CAD", ttk.Entry(controls, textvariable=self.initial, width=12)), ("End date", ttk.Entry(controls, textvariable=self.end_date, width=13))]
        for column, (label, widget) in enumerate(fields):
            ttk.Label(controls, text=label, style="Panel.TLabel").grid(row=0, column=column, sticky="w", padx=(0, 8))
            widget.grid(row=1, column=column, sticky="ew", padx=(0, 16))
        ttk.Checkbutton(controls, text="Reinvest dividends", variable=self.reinvest).grid(row=1, column=4, sticky="w", padx=4)
        ttk.Checkbutton(controls, text="Common start date", variable=self.common_start).grid(row=1, column=5, sticky="w", padx=4)
        selection = ttk.Frame(controls, style="Panel.TFrame")
        selection.grid(row=2, column=0, columnspan=4, sticky="w", pady=(16, 0))
        ttk.Label(selection, text="Compare ETFs", style="Panel.TLabel").pack(side="left", padx=(0, 14))
        for symbol, config in ETF_OPTIONS.items():
            ttk.Checkbutton(selection, text=f"{symbol}  ·  {config['ticker']}", variable=self.selected[symbol]).pack(side="left", padx=(0, 16))
        self.calculate_button = ttk.Button(controls, text="Calculate returns", command=self.calculate)
        self.calculate_button.grid(row=2, column=5, sticky="e", pady=(14, 0))
        controls.columnconfigure(5, weight=1)
        ttk.Label(outer, textvariable=self.status_var, style="Muted.TLabel").pack(anchor="w", pady=(0, 3))
        self.progress.pack(fill="x", pady=(0, 10))
        self.figure = plt.Figure(figsize=(10, 5), dpi=100, facecolor=BG)
        self.ax_line = self.figure.add_subplot(121)
        self.ax_bar = self.figure.add_subplot(122)
        self.canvas = FigureCanvasTkAgg(self.figure, master=outer)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, pady=(0, 12))
        self.canvas.mpl_connect("motion_notify_event", self._hover)
        self.tooltip = None
        self.summary_frame = ttk.Frame(outer)
        self.summary_frame.pack(fill="x")
        ttk.Label(outer, text="Historical performance does not guarantee future returns. This educational tool uses closing prices, assumes fractional shares, and excludes taxes and commissions.", style="Muted.TLabel", wraplength=1200).pack(anchor="w", pady=(12, 0))
        self._draw_empty()

    def _draw_empty(self) -> None:
        for axis in (self.ax_line, self.ax_bar):
            axis.set_facecolor(PANEL)
            axis.tick_params(colors=MUTED, labelsize=8)
            for spine in axis.spines.values(): spine.set_color(GRID)
        self.ax_line.set_title("Portfolio growth", color=TEXT, loc="left", fontsize=12, pad=12)
        self.ax_line.text(.5, .5, "Calculate returns to see your scenarios", ha="center", va="center", color=MUTED, transform=self.ax_line.transAxes)
        self.ax_bar.set_title("Contributions vs. growth", color=TEXT, loc="left", fontsize=12, pad=12)
        self.ax_bar.text(.5, .5, "Your comparison will appear here", ha="center", va="center", color=MUTED, transform=self.ax_bar.transAxes)
        self.figure.tight_layout(pad=2)
        self.canvas.draw_idle()

    def _parse_inputs(self) -> tuple[int, float, float, date]:
        try:
            year = int(self.start_year.get())
            amount = float(self.amount.get().replace(",", ""))
            initial = float(self.initial.get().replace(",", ""))
            end = datetime.strptime(self.end_date.get().strip(), "%Y-%m-%d").date()
        except (ValueError, TypeError) as error:
            raise ValueError("Enter a valid year, dollar amount, and end date in YYYY-MM-DD format.") from error
        if amount <= 0 or initial < 0: raise ValueError("Biweekly investment must be positive and initial investment cannot be negative.")
        if end < date(year, 1, 1): raise ValueError("End date must be on or after the selected start year.")
        if not any(var.get() for var in self.selected.values()): raise ValueError("Select at least one ETF.")
        return year, amount, initial, end

    def calculate(self) -> None:
        try:
            inputs = self._parse_inputs()
        except ValueError as error:
            messagebox.showerror("Check your inputs", str(error))
            return
        self.calculate_button.configure(state="disabled")
        self.progress.start(10)
        self.status_var.set("Preparing historical data…")
        threading.Thread(target=self._worker, args=inputs, daemon=True).start()

    def _worker(self, year: int, amount: float, initial: float, end: date) -> None:
        try:
            data_service = MarketData(lambda message: self.after(0, self.status_var.set, message))
            symbols = [symbol for symbol, var in self.selected.items() if var.get()]
            raw = {symbol: data_service.load(symbol, end) for symbol in symbols}
            starts = {symbol: (frame.loc[frame.index >= pd.Timestamp(year, 1, 1)].index[0] if not frame.loc[frame.index >= pd.Timestamp(year, 1, 1)].empty else frame.index[0]) for symbol, frame in raw.items()}
            forced = max(starts.values()) if self.common_start.get() else None
            results = {symbol: simulate(symbol, frame, year, end, amount, initial, self.reinvest.get(), forced) for symbol, frame in raw.items()}
            self.after(0, self._show_results, results)
        except Exception as error:  # network/library failures should return to the UI safely
            self.after(0, self._show_error, str(error))

    def _show_error(self, error: str) -> None:
        self.progress.stop(); self.calculate_button.configure(state="normal")
        self.status_var.set("Unable to calculate returns.")
        messagebox.showerror("Data error", f"{error}\n\nCheck your connection or try a smaller date range.")

    def _show_results(self, results: dict[str, Simulation]) -> None:
        self.results = results
        self.progress.stop(); self.calculate_button.configure(state="normal")
        self.status_var.set("Calculation complete — figures use downloaded historical closing data.")
        self._draw_charts()
        self._draw_summary()

    def _draw_charts(self) -> None:
        self.figure.clear(); self.ax_line = self.figure.add_subplot(121); self.ax_bar = self.figure.add_subplot(122)
        for axis in (self.ax_line, self.ax_bar):
            axis.set_facecolor(PANEL); axis.tick_params(colors=MUTED, labelsize=8)
            axis.grid(True, color=GRID, linewidth=.7, alpha=.8)
            for spine in axis.spines.values(): spine.set_color(GRID)
        for symbol, result in self.results.items():
            color = ETF_OPTIONS[symbol]["color"]
            self.ax_line.plot(result.dates, result.values, color=color, linewidth=2, label=f"{symbol} portfolio")
            self.ax_line.plot(result.dates, result.contributions, color=color, linewidth=1, linestyle="--", alpha=.55, label=f"{symbol} contributions")
        self.ax_line.set_title("Portfolio growth", color=TEXT, loc="left", fontsize=12, pad=12)
        self.ax_line.set_ylabel("CAD", color=MUTED); self.ax_line.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value:,.0f}"))
        self.ax_line.xaxis.set_major_locator(mdates.AutoDateLocator()); self.ax_line.xaxis.set_major_formatter(mdates.ConciseDateFormatter(self.ax_line.xaxis.get_major_locator()))
        legend = self.ax_line.legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, loc="upper left")
        if legend: legend.get_frame().set_alpha(.9)
        symbols = list(self.results); totals = [self.results[s].total_contributed for s in symbols]; growth = [self.results[s].growth for s in symbols]
        x = list(range(len(symbols)))
        self.ax_bar.bar(x, totals, color="#596473", label="Contributed")
        positive = [max(0, item) for item in growth]; negative = [min(0, item) for item in growth]
        self.ax_bar.bar(x, positive, bottom=totals, color="#55d6a4", label="Growth")
        self.ax_bar.bar(x, negative, color="#e57474", label="Loss")
        for index, symbol in enumerate(symbols): self.ax_bar.text(index, totals[index] + positive[index] + max(totals[index] * .025, 10), money(self.results[symbol].final_value), ha="center", color=TEXT, fontsize=8)
        self.ax_bar.set_xticks(x, symbols); self.ax_bar.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value:,.0f}")); self.ax_bar.set_title("Contributions vs. growth", color=TEXT, loc="left", fontsize=12, pad=12)
        self.ax_bar.legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT)
        self.figure.tight_layout(pad=2); self.canvas.draw_idle()

    def _draw_summary(self) -> None:
        for child in self.summary_frame.winfo_children(): child.destroy()
        for column, symbol in enumerate(self.results):
            result = self.results[symbol]
            card = ttk.Frame(self.summary_frame, style="Panel.TFrame", padding=12); card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0)); self.summary_frame.columnconfigure(column, weight=1)
            ttk.Label(card, text=symbol, style="Panel.TLabel", font=("Segoe UI Semibold", 12)).pack(anchor="w")
            fallback_note = "\n⚠ Starts at earliest available history" if result.start.year > self.start_year.get() else ""
            ttk.Label(card, text=f"{ETF_OPTIONS[symbol]['name']}\n{result.start:%b %Y} → {result.end:%b %Y}{fallback_note}", style="Muted.TLabel", wraplength=280).pack(anchor="w", pady=(2, 8))
            metrics = [("Contributed", money(result.total_contributed)), ("Portfolio value", money(result.final_value)), ("Investment growth", money(result.growth)), ("Total return", f"{result.return_pct:+.2f}%"), ("Money-weighted return", "—" if result.xirr is None else f"{result.xirr * 100:+.2f}% XIRR"), ("Contributions", str(result.contribution_count)), ("Duration", result.duration)]
            if not self.reinvest.get(): metrics.append(("Cash dividends", money(result.cash_received)))
            for label, value in metrics:
                row = ttk.Frame(card, style="Panel.TFrame"); row.pack(fill="x", pady=1); ttk.Label(row, text=label, style="Muted.TLabel").pack(side="left"); value_label = ttk.Label(row, text=value, style="Panel.TLabel"); value_label.pack(side="right")
                if label in ("Investment growth", "Total return", "Money-weighted return"): value_label.configure(foreground="#55d6a4" if result.growth >= 0 else "#e57474")
        ttk.Button(self.summary_frame, text="Export summary CSV", command=self.export_csv).grid(row=1, column=0, columnspan=max(1, len(self.results)), sticky="e", pady=(10, 0))

    def _hover(self, event) -> None:
        if event.inaxes != self.ax_line or not self.results or event.xdata is None: return
        target = mdates.num2date(event.xdata).replace(tzinfo=None)
        lines = []
        for symbol, result in self.results.items():
            position = result.dates.searchsorted(pd.Timestamp(target), side="right") - 1
            if position >= 0:
                value = float(result.values.iloc[position]); contribution = float(result.contributions.iloc[position]); lines.append(f"{symbol}: {money(value)}  ·  contributed {money(contribution)}  ·  growth {money(value - contribution)}")
        if not lines: return
        if self.tooltip: self.tooltip.remove()
        self.tooltip = self.ax_line.annotate(pd.Timestamp(target).strftime("%Y-%m-%d") + "\n" + "\n".join(lines), xy=(event.xdata, event.ydata), xytext=(12, 12), textcoords="offset points", color=TEXT, bbox={"boxstyle": "round,pad=.5", "fc": "#2a2f37", "ec": GRID})
        self.canvas.draw_idle()

    def export_csv(self) -> None:
        if not self.results: return
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile="biweekly_etf_summary.csv")
        if not filename: return
        fields = ["symbol", "ticker", "start_date", "end_date", "total_contributed_cad", "portfolio_value_cad", "cash_dividends_cad", "growth_cad", "return_percent", "xirr_percent", "contribution_count", "duration"]
        with open(filename, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields); writer.writeheader()
            for result in self.results.values(): writer.writerow({"symbol": result.symbol, "ticker": result.ticker, "start_date": result.start.date().isoformat(), "end_date": result.end.date().isoformat(), "total_contributed_cad": round(result.total_contributed, 2), "portfolio_value_cad": round(result.final_value, 2), "cash_dividends_cad": round(result.cash_received, 2), "growth_cad": round(result.growth, 2), "return_percent": round(result.return_pct, 4), "xirr_percent": None if result.xirr is None else round(result.xirr * 100, 4), "contribution_count": result.contribution_count, "duration": result.duration})
        self.status_var.set(f"Exported {len(self.results)} ETF summaries to {Path(filename).name}.")


if __name__ == "__main__":
    App().mainloop()

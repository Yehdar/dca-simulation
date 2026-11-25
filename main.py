"""Tkinter UI for the historical ETF backtesting engine."""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import FuncFormatter
from tkinter import filedialog, messagebox, ttk

from finance import (
    DIVIDEND_MODES,
    ETF_OPTIONS,
    PORTFOLIO_TEMPLATES,
    REBALANCING,
    MarketData,
    Simulation,
    load_portfolios,
    portfolio_allocations_valid,
    risk_metrics,
    rolling_returns,
    save_portfolios,
    simulate_portfolio,
    simulate_single,
    trading_schedule,
)

BG, PANEL, TEXT, MUTED, GRID = "#17191d", "#20242a", "#eef1f5", "#9aa4b2", "#343a43"
POSITIVE, NEGATIVE = "#55d6a4", "#e57474"
CACHE_DIR = Path(__file__).with_name(".market_cache")
PORTFOLIO_FILE = Path(__file__).with_name("portfolios.json")


def latest_weekday() -> date:
    current = date.today()
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def money(value: float) -> str:
    return f"${float(value):,.2f}"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Biweekly ETF Investor")
        self.geometry("1460x1000")
        self.minsize(1100, 760)
        self.configure(bg=BG)
        self._configure_style()
        self._init_state()
        self._build_ui()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 20))
        style.configure("TButton", background="#4d8edc", foreground="white", padding=(12, 7), borderwidth=0, font=("Segoe UI Semibold", 10))
        style.map("TButton", background=[("active", "#6da7ed")])
        style.configure("TEntry", fieldbackground="#2a2f37", foreground=TEXT, insertcolor=TEXT, borderwidth=0, padding=7)
        style.configure("TCombobox", fieldbackground="#2a2f37", foreground=TEXT, arrowcolor=TEXT, padding=6)
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=28, borderwidth=0)
        style.configure("Treeview.Heading", background="#2a2f37", foreground=TEXT, font=("Segoe UI Semibold", 9))
        style.configure("Horizontal.TProgressbar", troughcolor="#2a2f37", background="#5ea7ff")

    def _init_state(self) -> None:
        self.start_year = tk.IntVar(value=max(2015, date.today().year - 10))
        self.amount = tk.StringVar(value="500")
        self.initial = tk.StringVar(value="0")
        self.end_date = tk.StringVar(value=latest_weekday().isoformat())
        self.dividend_mode = tk.StringVar(value="Reinvest dividends (DRIP)")
        self.common_period = tk.BooleanVar(value=True)
        self.risk_free = tk.StringVar(value="2.0")
        self.rolling_years = tk.IntVar(value=5)
        self.rebalance = tk.StringVar(value=REBALANCING[0])
        self.status = tk.StringVar(value="Ready — select assumptions and calculate.")
        self.progress = ttk.Progressbar(self, mode="indeterminate", style="Horizontal.TProgressbar")
        self.selected = {symbol: tk.BooleanVar(value=True) for symbol in ETF_OPTIONS}
        self.portfolio_selected: dict[str, tk.BooleanVar] = {}
        self.custom_portfolios = load_portfolios(PORTFOLIO_FILE)
        self.frames: dict[str, pd.DataFrame] = {}
        self.results: dict[str, Simulation] = {}
        self.risk_results: dict[str, dict] = {}

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Biweekly ETF Investor", style="Header.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Historical portfolio backtesting with rolling returns, risk analysis, and custom allocations.", style="Muted.TLabel").pack(anchor="w", pady=(2, 12))
        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)
        self.growth_tab = ttk.Frame(self.notebook, padding=14)
        self.rolling_tab = ttk.Frame(self.notebook, padding=14)
        self.risk_tab = ttk.Frame(self.notebook, padding=14)
        self.builder_tab = ttk.Frame(self.notebook, padding=14)
        self.comparison_tab = ttk.Frame(self.notebook, padding=14)
        for tab, label in ((self.growth_tab, "Portfolio Growth"), (self.rolling_tab, "Rolling Returns"), (self.risk_tab, "Risk Analysis"), (self.builder_tab, "Portfolio Builder"), (self.comparison_tab, "Performance Comparison")):
            self.notebook.add(tab, text=label)
        self._build_growth_tab()
        self._build_rolling_tab()
        self._build_risk_tab()
        self._build_builder_tab()
        self._build_comparison_tab()
        ttk.Label(outer, textvariable=self.status, style="Muted.TLabel").pack(anchor="w", pady=(8, 2))
        self.progress.pack(fill="x")

    def _build_growth_tab(self) -> None:
        panel = ttk.Frame(self.growth_tab, style="Panel.TFrame", padding=14)
        panel.pack(fill="x", pady=(0, 10))
        ttk.Label(panel, text="Investment assumptions", style="Panel.TLabel", font=("Segoe UI Semibold", 11)).grid(row=0, column=0, columnspan=8, sticky="w", pady=(0, 8))
        fields = [("Start year", self.start_year), ("Biweekly CAD", self.amount), ("Initial CAD", self.initial), ("End date", self.end_date)]
        for column, (label, variable) in enumerate(fields):
            ttk.Label(panel, text=label, style="Panel.TLabel").grid(row=1, column=column, sticky="w")
            if label == "Start year":
                widget = ttk.Combobox(panel, textvariable=variable, values=list(range(1990, date.today().year + 1)), state="readonly", width=10)
            else:
                widget = ttk.Entry(panel, textvariable=variable, width=14)
            widget.grid(row=2, column=column, sticky="ew", padx=(0, 12))
        ttk.Label(panel, text="Dividend handling", style="Panel.TLabel").grid(row=1, column=4, sticky="w")
        ttk.Combobox(panel, textvariable=self.dividend_mode, values=list(DIVIDEND_MODES), state="readonly", width=30).grid(row=2, column=4, sticky="ew", padx=(0, 10))
        ttk.Checkbutton(panel, text="Use common investment period", variable=self.common_period).grid(row=2, column=5, sticky="w")
        ttk.Button(panel, text="Calculate returns", command=self.calculate).grid(row=2, column=6, sticky="e")
        for column in range(7): panel.columnconfigure(column, weight=1)
        self.selection_frame = ttk.Frame(panel, style="Panel.TFrame")
        self.selection_frame.grid(row=3, column=0, columnspan=7, sticky="ew", pady=(12, 0))
        self._refresh_selection_controls()
        self.growth_figure = plt.Figure(figsize=(12, 6), dpi=100, facecolor=BG)
        self.growth_ax, self.growth_bar = self.growth_figure.subplots(2, 1, height_ratios=(2, 1))
        self.canvas_growth = FigureCanvasTkAgg(self.growth_figure, master=self.growth_tab)
        self.canvas_growth.get_tk_widget().pack(fill="both", expand=True)
        self._empty_axes(self.growth_ax, "Portfolio growth")
        self._empty_axes(self.growth_bar, "Contributions vs. investment growth")

    def _refresh_selection_controls(self) -> None:
        for child in self.selection_frame.winfo_children(): child.destroy()
        ttk.Label(self.selection_frame, text="Compare", style="Panel.TLabel").pack(side="left", padx=(0, 12))
        for symbol in ETF_OPTIONS:
            ttk.Checkbutton(self.selection_frame, text=symbol, variable=self.selected[symbol]).pack(side="left", padx=(0, 12))
        for name in self.custom_portfolios:
            self.portfolio_selected.setdefault(name, tk.BooleanVar(value=False))
            ttk.Checkbutton(self.selection_frame, text=name, variable=self.portfolio_selected[name]).pack(side="left", padx=(0, 12))

    def _build_rolling_tab(self) -> None:
        panel = ttk.Frame(self.rolling_tab, style="Panel.TFrame", padding=12)
        panel.pack(fill="x", pady=(0, 10))
        ttk.Label(panel, text="Investment window", style="Panel.TLabel").pack(side="left")
        ttk.Combobox(panel, textvariable=self.rolling_years, values=[1, 2, 3, 5, 10, 15, 20], state="readonly", width=8).pack(side="left", padx=8)
        ttk.Button(panel, text="Run rolling backtest", command=self.calculate).pack(side="left", padx=8)
        ttk.Label(panel, text="Overlapping windows are not independent observations; historical profitability is not a future probability.", style="PanelMuted.TLabel").pack(side="left", padx=14)
        self.rolling_figure = plt.Figure(figsize=(12, 7), dpi=100, facecolor=BG)
        self.rolling_axes = self.rolling_figure.subplots(3, 1)
        self.canvas_rolling = FigureCanvasTkAgg(self.rolling_figure, master=self.rolling_tab)
        self.canvas_rolling.get_tk_widget().pack(fill="both", expand=True)
        for axis, title in zip(self.rolling_axes, ("Rolling annualized money-weighted returns", "Return distribution", "Return comparison box plots")): self._empty_axes(axis, title)
        columns = ("name", "average", "median", "best", "worst", "std", "avg_value", "profitable")
        self.rolling_table = ttk.Treeview(self.rolling_tab, columns=columns, show="headings", height=5)
        for column in columns: self.rolling_table.heading(column, text=column.replace("_", " ").title()); self.rolling_table.column(column, width=125)
        self.rolling_table.pack(fill="x", pady=(10, 0))

    def _build_risk_tab(self) -> None:
        panel = ttk.Frame(self.risk_tab, style="Panel.TFrame", padding=12)
        panel.pack(fill="x", pady=(0, 10))
        ttk.Label(panel, text="Annual risk-free rate (%)", style="Panel.TLabel").pack(side="left")
        ttk.Entry(panel, textvariable=self.risk_free, width=8).pack(side="left", padx=8)
        ttk.Button(panel, text="Recalculate risk", command=self.calculate).pack(side="left")
        self.risk_figure = plt.Figure(figsize=(12, 6), dpi=100, facecolor=BG)
        self.risk_axes = self.risk_figure.subplots(1, 2)
        self.canvas_risk = FigureCanvasTkAgg(self.risk_figure, master=self.risk_tab)
        self.canvas_risk.get_tk_widget().pack(fill="both", expand=True)
        self._empty_axes(self.risk_axes[0], "Maximum drawdown")
        self._empty_axes(self.risk_axes[1], "Risk / return")
        columns = ("name", "drawdown", "volatility", "sharpe", "best", "worst", "recovery")
        self.risk_table = ttk.Treeview(self.risk_tab, columns=columns, show="headings", height=5)
        for column in columns: self.risk_table.heading(column, text=column.title()); self.risk_table.column(column, width=130)
        self.risk_table.pack(fill="x", pady=(10, 0))

    def _build_builder_tab(self) -> None:
        left = ttk.Frame(self.builder_tab, style="Panel.TFrame", padding=14); left.pack(side="left", fill="y", padx=(0, 10))
        right = ttk.Frame(self.builder_tab, style="Panel.TFrame", padding=14); right.pack(side="left", fill="both", expand=True)
        self.portfolio_name = tk.StringVar(value="My Portfolio")
        self.alloc_vars = {symbol: tk.StringVar(value="33.33") for symbol in ETF_OPTIONS}
        ttk.Label(left, text="Portfolio builder", style="Panel.TLabel", font=("Segoe UI Semibold", 12)).pack(anchor="w")
        ttk.Label(left, text="Name", style="Panel.TLabel").pack(anchor="w", pady=(14, 2)); ttk.Entry(left, textvariable=self.portfolio_name, width=25).pack(anchor="w")
        for symbol in ETF_OPTIONS:
            ttk.Label(left, text=f"{symbol} allocation (%)", style="Panel.TLabel").pack(anchor="w", pady=(10, 2)); ttk.Entry(left, textvariable=self.alloc_vars[symbol], width=12).pack(anchor="w")
        self.allocation_status = ttk.Label(left, text="Total: 99.99%", style="PanelMuted.TLabel"); self.allocation_status.pack(anchor="w", pady=8)
        ttk.Label(left, text="Rebalancing", style="Panel.TLabel").pack(anchor="w", pady=(8, 2)); ttk.Combobox(left, textvariable=self.rebalance, values=REBALANCING, state="readonly", width=30).pack(anchor="w")
        ttk.Button(left, text="Save portfolio", command=self.save_portfolio).pack(anchor="w", pady=(12, 4)); ttk.Button(left, text="Delete selected", command=self.delete_portfolio).pack(anchor="w")
        ttk.Label(left, text="Templates", style="Panel.TLabel").pack(anchor="w", pady=(20, 4)); self.template_combo = ttk.Combobox(left, values=list(PORTFOLIO_TEMPLATES), state="readonly", width=25); self.template_combo.pack(anchor="w"); self.template_combo.bind("<<ComboboxSelected>>", self.apply_template)
        ttk.Label(right, text="Saved portfolios", style="Panel.TLabel", font=("Segoe UI Semibold", 12)).pack(anchor="w")
        self.portfolio_list = tk.Listbox(right, bg=PANEL, fg=TEXT, selectbackground="#4d8edc", borderwidth=0, highlightthickness=0, height=8); self.portfolio_list.pack(fill="x", pady=(10, 0)); self.portfolio_list.bind("<<ListboxSelect>>", self.load_selected_portfolio)
        self.builder_figure = plt.Figure(figsize=(5, 4), dpi=100, facecolor=BG); self.builder_ax = self.builder_figure.add_subplot(111); self.builder_canvas = FigureCanvasTkAgg(self.builder_figure, master=right); self.builder_canvas.get_tk_widget().pack(fill="both", expand=True, pady=15)
        self._refresh_portfolio_list(); self._draw_allocation()

    def _build_comparison_tab(self) -> None:
        top = ttk.Frame(self.comparison_tab); top.pack(fill="x", pady=(0, 10)); ttk.Label(top, text="Sortable comparison table. Click a column heading to sort.", style="Muted.TLabel").pack(side="left"); ttk.Button(top, text="Export CSV", command=self.export_csv).pack(side="right")
        columns = ("name", "duration", "contributed", "value", "growth", "return", "xirr", "twr", "drawdown", "volatility", "sharpe", "dividends")
        self.summary_tree = ttk.Treeview(self.comparison_tab, columns=columns, show="headings")
        headings = {"name": "ETF / Portfolio", "duration": "Duration", "contributed": "Contributed", "value": "Final value", "growth": "Growth", "return": "Return %", "xirr": "XIRR", "twr": "TWR", "drawdown": "Max DD", "volatility": "Volatility", "sharpe": "Sharpe", "dividends": "Cash dividends"}
        for column in columns:
            self.summary_tree.heading(column, text=headings[column], command=lambda c=column: self.sort_tree(c, False)); self.summary_tree.column(column, width=115, anchor="e")
        self.summary_tree.column("name", width=180, anchor="w"); self.summary_tree.pack(fill="both", expand=True)

    def _empty_axes(self, axis: Any, title: str) -> None:
        axis.set_facecolor(PANEL); axis.tick_params(colors=MUTED, labelsize=8); axis.grid(True, color=GRID, linewidth=.7, alpha=.8)
        for spine in axis.spines.values(): spine.set_color(GRID)
        axis.set_title(title, color=TEXT, loc="left", fontsize=11, pad=10)

    def _selected_names(self) -> list[str]:
        return [symbol for symbol, value in self.selected.items() if value.get()] + [name for name, value in self.portfolio_selected.items() if value.get()]

    def _parse_inputs(self) -> tuple[int, float, float, date]:
        try: year, amount, initial = int(self.start_year.get()), float(self.amount.get().replace(",", "")), float(self.initial.get().replace(",", "")); end = datetime.strptime(self.end_date.get().strip(), "%Y-%m-%d").date()
        except (ValueError, TypeError) as error: raise ValueError("Use numeric amounts and an end date in YYYY-MM-DD format.") from error
        if amount <= 0 or initial < 0: raise ValueError("Biweekly investment must be positive and initial investment cannot be negative.")
        if end < date(year, 1, 1): raise ValueError("End date must be on or after the selected start year.")
        if not self._selected_names(): raise ValueError("Select at least one ETF or custom portfolio.")
        return year, amount, initial, end

    def calculate(self) -> None:
        try: inputs = self._parse_inputs()
        except ValueError as error: messagebox.showerror("Check inputs", str(error)); return
        self.progress.start(10); self.status.set("Loading cached historical data…")
        threading.Thread(target=self._worker, args=inputs, daemon=True).start()

    def _worker(self, year: int, amount: float, initial: float, end: date) -> None:
        try:
            names = self._selected_names(); underlying = set(symbol for symbol in names if symbol in ETF_OPTIONS)
            for name in names:
                if name in self.custom_portfolios: underlying.update(symbol for symbol, weight in self.custom_portfolios[name].items() if weight > 0)
            service = MarketData(CACHE_DIR, lambda message: self.after(0, self.status.set, message)); frames = {symbol: service.load(symbol, end) for symbol in underlying}
            requested = pd.Timestamp(year, 1, 1)
            starts = {symbol: frame.index[frame.index >= requested][0] if not frame.loc[frame.index >= requested].empty else frame.index[0] for symbol, frame in frames.items()}
            common_start = max(starts.values()) if self.common_period.get() else None; common_end = min(frame.index[-1] for frame in frames.values()) if self.common_period.get() else None
            if common_start is not None and common_end is not None and common_start >= common_end: raise ValueError("The selected investments have no overlapping historical period.")
            mode = DIVIDEND_MODES[self.dividend_mode.get()]; results: dict[str, Simulation] = {}
            if common_start is not None and common_end is not None:
                shared_index = pd.DatetimeIndex(sorted(set.intersection(*(set(frame.index) for frame in frames.values())))); schedule = trading_schedule(shared_index, common_start, common_end)
            else: schedule = None
            for name in names:
                if name in ETF_OPTIONS:
                    start, finish = (common_start, common_end) if common_start is not None else (starts[name], frames[name].index[-1]); results[name] = simulate_single(name, frames[name], start, finish, amount, initial, mode, schedule)
                else:
                    allocation = self.custom_portfolios[name]; symbols = [symbol for symbol, weight in allocation.items() if weight > 0]; available = [frames[symbol].index[frames[symbol].index >= requested][0] if not frames[symbol].loc[frames[symbol].index >= requested].empty else frames[symbol].index[0] for symbol in symbols]; start, finish = (common_start, common_end) if common_start is not None else (max(available), min(frames[symbol].index[-1] for symbol in symbols)); results[name] = simulate_portfolio(name, allocation, frames, start, finish, amount, initial, mode, self.rebalance.get(), schedule)
            warning = ""
            if common_start is not None and common_end is not None and (common_start > requested or common_end.date() < end):
                warning = f" Requested period shortened to common data: {common_start.date()} → {common_end.date()}."
            self.after(0, self._finish, frames, results, mode, warning)
        except Exception as error: self.after(0, self._error, str(error))

    def _finish(self, frames: dict[str, pd.DataFrame], results: dict[str, Simulation], mode: str, warning: str = "") -> None:
        self.frames, self.results = frames, results; self.progress.stop(); self.status.set("Calculation complete — real historical data and selected assumptions applied." + warning)
        try: risk_rate = float(self.risk_free.get()) / 100
        except ValueError: risk_rate = .02
        self.risk_results = {name: risk_metrics(result, risk_rate) for name, result in results.items()}; self.draw_growth(); self.draw_risk(); self.draw_comparison(); self.run_rolling()

    def _error(self, error: str) -> None:
        self.progress.stop(); self.status.set("Calculation failed."); messagebox.showerror("Backtest error", error)

    def draw_growth(self) -> None:
        self.growth_figure.clear(); self.growth_ax, self.growth_bar = self.growth_figure.subplots(2, 1, height_ratios=(2, 1)); self._empty_axes(self.growth_ax, "Portfolio growth"); self._empty_axes(self.growth_bar, "Contributions vs. investment growth")
        for name, result in self.results.items():
            color = ETF_OPTIONS[result.symbols[0]]["color"] if result.symbols[0] in ETF_OPTIONS else "#f0a35e"; self.growth_ax.plot(result.dates, result.values, color=color, lw=2, label=name); self.growth_ax.plot(result.dates, result.contributions, color=color, ls="--", alpha=.45)
        self.growth_ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value:,.0f}")); self.growth_ax.legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT); self.growth_ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(self.growth_ax.xaxis.get_major_locator()))
        names = list(self.results); x = np.arange(len(names)); totals = [self.results[n].total_contributed for n in names]; growth = [self.results[n].growth for n in names]; self.growth_bar.bar(x, totals, color="#596473", label="Contributed"); self.growth_bar.bar(x, [max(0, value) for value in growth], bottom=totals, color=POSITIVE, label="Growth"); self.growth_bar.bar(x, [min(0, value) for value in growth], color=NEGATIVE, label="Loss"); self.growth_bar.set_xticks(x, names); self.growth_bar.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value:,.0f}")); self.growth_bar.legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT); self.growth_figure.tight_layout(pad=2); self.canvas_growth.draw_idle()

    def run_rolling(self) -> None:
        if not self.frames or not self.results: return
        try: amount, years, mode = float(self.amount.get().replace(",", "")), int(self.rolling_years.get()), DIVIDEND_MODES[self.dividend_mode.get()]
        except ValueError: return
        common_start = max(frame.index[0] for frame in self.frames.values()) if self.common_period.get() else None; common_end = min(frame.index[-1] for frame in self.frames.values()) if self.common_period.get() else None; self.rolling_data = {}
        for name, result in self.results.items():
            if len(result.symbols) == 1: self.rolling_data[name] = rolling_returns(result.symbols[0], self.frames[result.symbols[0]], years, amount, mode, common_start, common_end)
            else:
                rows = []; frame = self.frames[result.symbols[0]]; eligible = frame.index[(frame.index >= (common_start or frame.index[0])) & (frame.index + pd.DateOffset(years=years) <= (common_end or frame.index[-1]))]
                for start in eligible:
                    finish = frame.index[frame.index.searchsorted(start + pd.DateOffset(years=years), side="right") - 1]; sim = simulate_portfolio(name, self.custom_portfolios[name], self.frames, start, finish, amount, 0, mode, self.rebalance.get()); rows.append({"start": start, "end": finish, "return": sim.xirr, "final_value": sim.final_value, "profitable": sim.growth > 0})
                self.rolling_data[name] = pd.DataFrame(rows)
        self.draw_rolling()

    def draw_rolling(self) -> None:
        self.rolling_figure.clear(); self.rolling_axes = self.rolling_figure.subplots(3, 1); [self._empty_axes(axis, title) for axis, title in zip(self.rolling_axes, ("Rolling annualized money-weighted returns", "Return distribution", "Return comparison box plots"))]
        for name, frame in self.rolling_data.items():
            if frame.empty: continue
            color = ETF_OPTIONS[self.results[name].symbols[0]]["color"] if self.results[name].symbols[0] in ETF_OPTIONS else "#f0a35e"; values = frame["return"].dropna() * 100; self.rolling_axes[0].plot(frame["end"], frame["return"] * 100, color=color, lw=1.1, label=name); self.rolling_axes[1].hist(values, bins=24, alpha=.4, color=color, label=name); self.rolling_axes[2].boxplot(values, positions=[list(self.rolling_data).index(name) + 1], widths=.5, patch_artist=True, boxprops={"facecolor": color}, medianprops={"color": TEXT}); self.rolling_table.insert("", "end", values=(name, f"{values.mean():.2f}%", f"{values.median():.2f}%", f"{values.max():.2f}%", f"{values.min():.2f}%", f"{values.std():.2f}%", money(frame["final_value"].mean()), f"{frame['profitable'].mean() * 100:.1f}%"))
        self.rolling_axes[0].axhline(0, color=GRID); self.rolling_axes[0].set_ylabel("Annualized %", color=MUTED); self.rolling_axes[0].legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT); self.rolling_axes[1].set_xlabel("Annualized return (%)", color=MUTED); self.rolling_axes[1].legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT); self.rolling_axes[2].set_xticks(range(1, len(self.rolling_data) + 1), list(self.rolling_data)); self.rolling_axes[2].set_ylabel("Annualized %", color=MUTED); self.rolling_figure.tight_layout(pad=2); self.canvas_rolling.draw_idle()

    def draw_risk(self) -> None:
        self.risk_figure.clear(); self.risk_axes = self.risk_figure.subplots(1, 2); [self._empty_axes(axis, title) for axis, title in zip(self.risk_axes, ("Maximum drawdown", "Risk / return"))]
        for name, result in self.results.items():
            color = ETF_OPTIONS[result.symbols[0]]["color"] if result.symbols[0] in ETF_OPTIONS else "#f0a35e"; self.risk_axes[0].plot(result.dates, self.risk_results[name]["drawdown_series"] * 100, color=color, label=name); self.risk_axes[1].scatter(self.risk_results[name]["volatility"] * 100, (result.time_weighted_return or 0) * 100, color=color, s=70, label=name)
        self.risk_axes[0].set_ylabel("Drawdown (%)", color=MUTED); self.risk_axes[0].legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT); self.risk_axes[1].set_xlabel("Annualized volatility (%)", color=MUTED); self.risk_axes[1].set_ylabel("Time-weighted return (%)", color=MUTED); self.risk_axes[1].legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT); self.risk_figure.tight_layout(pad=2); self.canvas_risk.draw_idle()
        for item in self.risk_table.get_children(): self.risk_table.delete(item)
        for name, result in self.results.items():
            risk = self.risk_results[name]; self.risk_table.insert("", "end", values=(name, f"{risk['max_drawdown'] * 100:.2f}%", f"{risk['volatility'] * 100:.2f}%", "—" if risk["sharpe"] is None else f"{risk['sharpe']:.2f}", "—" if risk["best_year"] is None else f"{risk['best_year'] * 100:.2f}%", "—" if risk["worst_year"] is None else f"{risk['worst_year'] * 100:.2f}%", risk["recovery_text"]))

    def draw_comparison(self) -> None:
        for item in self.summary_tree.get_children(): self.summary_tree.delete(item)
        for name, result in self.results.items():
            risk = self.risk_results[name]; self.summary_tree.insert("", "end", values=(name, result.duration_text, money(result.total_contributed), money(result.final_value), money(result.growth), f"{result.return_pct:+.2f}%", "—" if result.xirr is None else f"{result.xirr * 100:+.2f}%", "—" if result.time_weighted_return is None else f"{result.time_weighted_return * 100:+.2f}%", f"{risk['max_drawdown'] * 100:.2f}%", f"{risk['volatility'] * 100:.2f}%", "—" if risk['sharpe'] is None else f"{risk['sharpe']:.2f}", money(result.cash_received)))

    def sort_tree(self, column: str, reverse: bool) -> None:
        items = [(self.summary_tree.set(item, column), item) for item in self.summary_tree.get_children("")]
        try: items.sort(key=lambda value: float(value[0].replace("$", "").replace(",", "").replace("%", "")), reverse=reverse)
        except ValueError: items.sort(reverse=reverse)
        for index, (_, item) in enumerate(items): self.summary_tree.move(item, "", index)
        self.summary_tree.heading(column, command=lambda: self.sort_tree(column, not reverse))

    def _refresh_portfolio_list(self) -> None:
        self.portfolio_list.delete(0, "end")
        for name in self.custom_portfolios: self.portfolio_list.insert("end", name)

    def apply_template(self, _event: Any = None) -> None:
        for symbol, value in PORTFOLIO_TEMPLATES[self.template_combo.get()].items(): self.alloc_vars[symbol].set(f"{value * 100:.2f}")
        self._draw_allocation()

    def _draw_allocation(self) -> None:
        try:
            values = [max(0, float(self.alloc_vars[symbol].get())) for symbol in ETF_OPTIONS]; total = sum(values); self.allocation_status.configure(text=f"Total: {total:.2f}%", foreground=POSITIVE if abs(total - 100) < .01 else NEGATIVE); self.builder_ax.clear(); self.builder_ax.set_facecolor(BG); self.builder_ax.pie(values or [1], labels=list(ETF_OPTIONS), colors=[ETF_OPTIONS[s]["color"] for s in ETF_OPTIONS], textprops={"color": TEXT}); self.builder_canvas.draw_idle()
        except ValueError: self.allocation_status.configure(text="Enter numeric percentages", foreground=NEGATIVE)

    def save_portfolio(self) -> None:
        try: allocations = {symbol: float(self.alloc_vars[symbol].get()) / 100 for symbol in ETF_OPTIONS}
        except ValueError: messagebox.showerror("Invalid allocation", "Allocations must be numeric percentages."); return
        if not portfolio_allocations_valid(allocations): messagebox.showerror("Invalid allocation", "Allocations must be between 0% and 100% and total exactly 100%."); return
        name = self.portfolio_name.get().strip()
        if not name: messagebox.showerror("Invalid name", "Enter a portfolio name."); return
        self.custom_portfolios[name] = allocations; self.portfolio_selected.setdefault(name, tk.BooleanVar(value=False)); save_portfolios(PORTFOLIO_FILE, self.custom_portfolios); self._refresh_portfolio_list(); self._refresh_selection_controls(); self._draw_allocation()

    def delete_portfolio(self) -> None:
        selected = self.portfolio_list.curselection()
        if not selected: return
        name = self.portfolio_list.get(selected[0]); self.custom_portfolios.pop(name, None); self.portfolio_selected.pop(name, None); save_portfolios(PORTFOLIO_FILE, self.custom_portfolios); self._refresh_portfolio_list(); self._refresh_selection_controls()

    def load_selected_portfolio(self, _event: Any = None) -> None:
        selected = self.portfolio_list.curselection()
        if not selected: return
        name = self.portfolio_list.get(selected[0]); self.portfolio_name.set(name)
        for symbol, value in self.custom_portfolios[name].items(): self.alloc_vars[symbol].set(f"{value * 100:.2f}")
        self._draw_allocation()

    def export_csv(self) -> None:
        if not self.results: return
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile="performance_comparison.csv")
        if not filename: return
        rows = []
        for name, result in self.results.items():
            risk = self.risk_results[name]; rows.append({"name": name, "duration": result.duration_text, "total_contributed_cad": result.total_contributed, "final_value_cad": result.final_value, "growth_cad": result.growth, "return_percent": result.return_pct, "xirr_percent": None if result.xirr is None else result.xirr * 100, "time_weighted_return_percent": None if result.time_weighted_return is None else result.time_weighted_return * 100, "max_drawdown_percent": risk["max_drawdown"] * 100, "annualized_volatility_percent": risk["volatility"] * 100, "sharpe_ratio": risk["sharpe"], "cash_dividends_cad": result.cash_received})
        pd.DataFrame(rows).to_csv(filename, index=False); self.status.set(f"Exported {len(rows)} performance rows to {Path(filename).name}.")


if __name__ == "__main__":
    App().mainloop()

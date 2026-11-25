# Biweekly ETF Investor

## Historical backtesting, portfolio risk and long-term investment strategy

**Research snapshot:** November 25, 2026 · **Currency:** CAD · **Data source:** Yahoo Finance via `yfinance`

## Executive summary

This project explores a deceptively simple question: if an investor consistently buys ETFs every two weeks, which investment produces the most wealth over time, and what risks accompany those returns?

The experiments compare three Canadian-listed equity ETFs: VFV, VDY and QQC. The results demonstrate that the ranking depends heavily on the investment period, the timing of contributions, dividend treatment and the market conditions near the end of the simulation.

The principal findings are:

- **VFV** offers broad exposure to large US companies and is a reasonable core holding.
- **VDY** delivered unusually strong returns and the best risk-adjusted performance in the recent sample, despite its concentration in Canadian financials and energy.
- **QQC** delivered the highest ending wealth in the common-period simulation ending January 20, 2026, but experienced the largest drawdowns and volatility.
- Recurring investors can benefit from early market declines if prices subsequently recover, but volatility itself does not guarantee higher returns.
- No historical winner can be assumed to be the future winner. A diversified allocation is a way to reduce dependence on that prediction.

**Proposed working strategy:** 50% VFV, 25% VDY and 25% QQC, with automatic biweekly contributions, reinvested distributions and annual rebalancing. This is an illustrative choice among these three funds, not a proven optimal allocation or a confirmed investment decision. A globally diversified equity ETF is a simpler alternative with broader geographic coverage.

## 1. Project overview

Biweekly ETF Investor is a Python desktop application intended to visualize dollar-cost averaging (DCA), compounding and historical portfolio risk using real market data.

The application shown in the research screenshots includes five tabs:

| Tab | Purpose |
|---|---|
| Portfolio Growth | Compare accumulated contributions, portfolio value and investment growth. |
| Rolling Returns | Evaluate multiple historical investment windows rather than one start/end pair. |
| Risk Analysis | Compare drawdowns, volatility, Sharpe ratios and recovery dates. |
| Portfolio Builder | Design combinations of ETFs and target allocations. |
| Performance Comparison | Compare investment and risk metrics in a single table. |

The intended stack is Python, Tkinter/ttk, yfinance, Pandas, NumPy and Matplotlib. The source repository was not supplied for this write-up; the screenshots establish visible outputs, not the correctness or completion of every proposed feature. Consult the actual repository for installation commands, dependencies and entry point.

## 2. Investments being compared

| ETF | Yahoo Finance symbol | Exposure | Primary consideration |
|---|---|---|---|
| Vanguard S&P 500 Index ETF | `VFV.TO` | Approximately 500 large US companies across sectors | Broad US equity exposure, but not global diversification |
| Vanguard FTSE Canadian High Dividend Yield Index ETF | `VDY.TO` | Dividend-paying Canadian equities | Heavy financial and energy sector concentration |
| Invesco NASDAQ 100 Index ETF | `QQC.TO` | Large non-financial Nasdaq-listed companies | Growth and technology concentration; substantial overlap with VFV |

All three trade in CAD. VFV and QQC have unhedged foreign-currency exposure, so changes in CAD/USD can affect Canadian-dollar returns. Trading in CAD does not eliminate currency risk.

VFV and QQC are not independent exposures: many of the largest Nasdaq companies are also major S&P 500 constituents. VDY adds different sectors and domestic exposure, but does not provide broad international diversification.

## 3. Simulation methodology

A fair comparison should apply the same initial capital, recurring contributions, trade dates, end date and dividend treatment to every strategy.

### Dollar-cost averaging

For a fixed contribution `C` and execution price `P(t)`:

```
shares purchased at t = C / P(t)
portfolio value at T = total shares accumulated × P(T)
net growth = portfolio value + uninvested distributions − total contributions
simple return = net growth / total contributions
```

For a multi-ETF portfolio, sum the values of each underlying holding and any retained cash. Contributions are allocated according to the portfolio weights, not duplicated across holdings.

Schedule deposits every 14 calendar days. If a deposit date falls on a weekend or exchange holiday, execute on the next valid trading day without shifting the original schedule. Do not count a scheduled deposit beyond the simulation end unless it is explicitly retained as cash. Fractional shares, zero commissions and no taxes are simplifying assumptions to verify in the implementation.

### Dividends

Three modes were proposed:

- **Reinvest distributions:** use dividend- and split-adjusted prices as a total-return proxy, or explicitly simulate reinvestment using consistent prices and distributions. Never do both.
- **Collect distributions:** track cash separately using eligible holdings and distribution data.
- **Price appreciation only:** exclude distributions while accounting for stock splits.

An adjusted-price simulation represents total-return units, not necessarily actual shares or a broker's exact DRIP mechanics. A zero cash-dividend balance in reinvestment mode does not mean no dividends were earned.

### Common investment period

The earliest valid shared start date is constrained by the ETF with the shortest history. QQC data in the screenshots begins around May 2021. When comparing all three funds, this restricts the available common history. Never extrapolate actual ETF prices before inception.

Use the same trading dates for every strategy. When comparing different end dates, hold the start date, deposit schedule, amount and dividend mode constant to isolate the end-date effect.

## 4. Historical experiment A: ending November 2026

The first screenshot reported these values:

| Metric | VFV | VDY | QQC |
|---|---:|---:|---:|
| Contributed | $327,200.00 | $327,200.00 | $309,200.00 |
| Final value | $543,120.48 | $639,228.02 | $521,454.11 |
| Investment growth | $215,920.48 | $312,028.02 | $212,254.11 |
| Simple return | 65.99% | 95.36% | 68.65% |
| XIRR | 14.95% | 19.80% | 16.51% |
| Contributions | 154 | 154 | 144 |
| Duration | 5y 10m | 5y 10m | 5y 5m |

VDY produced $96,107.54 more growth than VFV on identical reported contributions. QQC started later and received less capital, making absolute ending values unsuitable for a direct three-way comparison.

A separate one-year price comparison screenshot showed VDY +22.30%, VFV +4.48% and QQC +1.29%. Whether those figures include distributions was not established. They must not be treated as verified total returns.

### Why VDY can outperform technology-heavy funds

A successful business is not necessarily a successful investment at every price. Stock returns depend on earnings, distributions and changes in valuation. A company whose earnings rise 25% while its valuation multiple falls 20% can have a flat share price; a bank whose earnings rise 8% while its multiple rises 20% can appreciate 29.6%, before distributions.

VDY's financial and energy exposures can benefit when those sectors outperform. Its distributions contribute to total return when reinvested. Conversely, high expectations for technology companies can lead to weak stock performance even when their businesses grow. Currency moves can also affect VFV and QQC in CAD.

These are plausible explanations for the observed ranking, not a verified attribution of the exact historical returns. Higher dividend yield alone does not cause superior total return: distributions reduce fund value when paid, all else equal.

## 5. Historical experiment B: ending January 20, 2026

The second experiment removed the subsequent months of 2026 and enabled the common investment period. The inputs were $500 biweekly, $100 initial investment and reinvested distributions. The requested start year was 2021; the shared history produced a reported duration of 4 years and 8 months.

| Metric | VFV | VDY | QQC |
|---|---:|---:|---:|
| Total contributed | $61,100.00 | $61,100.00 | $61,100.00 |
| Final value | $92,099.41 | $95,069.12 | $99,466.03 |
| Growth | $30,999.41 | $33,969.12 | $38,366.03 |
| Simple return | 50.74% | 55.60% | 62.79% |
| XIRR | 17.95% | 19.37% | 21.41% |
| Cumulative TWR | 93.14% | 91.09% | 111.87% |
| Maximum drawdown | -22.08% | -16.18% | -31.70% |
| Annualized volatility | 15.00% | 11.60% | 21.01% |
| Sharpe ratio | 0.89 | 1.09 | 0.78 |

QQC finished $4,396.91 ahead of VDY and $7,366.62 ahead of VFV. VDY nevertheless had the strongest reported Sharpe ratio and smallest maximum drawdown.

Notably, VFV had a higher cumulative TWR than VDY, yet VDY had higher personal investment growth and XIRR. This illustrates how contribution timing can reverse the ranking of underlying fund returns.

The January screenshot and November screenshot differ in contributions and available start dates as well as end dates. They demonstrate sensitivity, but are not a controlled experiment isolating the effect of the last ten months. Rerun both with identical common-period settings to establish that effect precisely.

## 6. Understanding the performance metrics

| Metric | Meaning |
|---|---|
| Total contributions | Investor's own money deposited, including initial capital. |
| Investment growth | Ending wealth less external contributions. |
| Simple return | Growth divided by contributions; not an annual rate. |
| XIRR | Annualized money-weighted return, accounting for amounts and dates of external cash flows. |
| TWR | Compounded investment performance after removing the effect of external contributions and withdrawals. |
| Annualized TWR | Geometric annual equivalent of cumulative TWR over the measured period. |
| Maximum drawdown | Largest peak-to-trough percentage decline in the cash-flow-adjusted wealth index. |
| Annualized volatility | Standard deviation of periodic returns scaled to a year. |
| Sharpe ratio | Annualized excess return relative to annualized volatility. |
| Recovery date | First date after the maximum drawdown trough on which its prior peak is regained. |

For XIRR, solve `sum(CF_i / (1+r)^((date_i-date_0)/365)) = 0`, with deposits negative from the investor's perspective and ending wealth positive. Cash distributions retained inside the portfolio are part of ending wealth, not external withdrawals.

TWR chains subperiod returns around external cash flows. For contributions applied at the end of a daily period, a suitable daily return is `(V_today - contribution_today) / V_yesterday - 1`; beginning-of-period contributions require a different denominator. Use a consistent execution convention.

Drawdown is `wealth_index / running_max(wealth_index) - 1`. Annualized daily volatility is typically `std(daily_returns) × sqrt(252)`. For Sharpe, use consistent daily excess returns and annualize; do not divide cumulative TWR or XIRR by annualized volatility.

## 7. Rolling five-year returns

The rolling backtest shifts the start and end dates while preserving the five-year investment horizon. Each point represents one complete DCA investment window, rather than a single day's return.

| Metric | VFV | VDY | QQC |
|---|---:|---:|---:|
| Average XIRR | 19.74% | 24.50% | 24.68% |
| Median XIRR | 19.75% | 24.51% | 24.84% |
| Best XIRR | 21.03% | 26.21% | 27.65% |
| Worst XIRR | 17.24% | 21.97% | 19.50% |
| Standard deviation of window XIRRs | 0.74% | 0.84% | 1.78% |
| Average final value | $106,482.88 | $119,340.70 | $119,922.89 |
| Profitable windows | 100% | 100% | 100% |

QQC narrowly led in average return; VDY had the highest worst-case return; VFV had the narrowest distribution of outcomes. The histogram shows return frequencies and the box plot shows the median, middle 50%, whiskers and possible outliers.

**Critical limitation:** the plotted windows end only around May–November 2026. A window beginning May 2021 and one beginning November 2021 share roughly 90% of their histories. Hundreds of overlapping daily windows do not constitute hundreds of independent market cycles. The 100% profitable figure describes this narrow sample, not the probability of future success.

The rolling standard deviation measures variation between complete window returns. It is not the same as daily market volatility.

## 8. Risk analysis

The risk screenshot, with a 2% annual risk-free assumption, reported:

| Metric | VFV | VDY | QQC |
|---|---:|---:|---:|
| Maximum drawdown | -22.08% | -16.18% | -31.70% |
| Annualized volatility | 14.98% | 11.53% | 21.41% |
| Sharpe ratio | 0.82 | 1.20 | 0.69 |
| Best reported calendar-year return | 35.14% | 30.85% | 51.56% |
| Worst reported calendar-year return | -12.48% | -0.28% | -27.93% |
| Recovery date | 2023-07-19 | 2024-03-12 | 2023-08-31 |

A hypothetical $100,000 at each respective peak would fall to $77,920 in VFV, $83,820 in VDY and $68,300 in QQC at those historical troughs, ignoring new deposits.

VDY had the lowest measured risk and strongest reported Sharpe ratio. QQC offered the highest best-year return, but also the largest worst-year loss. Smaller drawdowns do not necessarily mean faster recoveries; measure time from the actual peak and trough dates.

The risk/return scatter plot uses cumulative TWR on its vertical axis and annualized volatility on its horizontal axis. Change the vertical axis to annualized TWR for more meaningful comparisons across durations. Compare full calendar years consistently and label partial years separately. These risk measures describe the selected sample, not an ETF's maximum possible future loss.

## 9. Why volatility can help recurring investors

Consider two hypothetical funds beginning at $100 and ending at $150. Invest $1,000 at each of five purchase dates, with no distributions or fees.

| Purchase | Steady fund price | Volatile fund price |
|---|---:|---:|
| 1 | $100 | $100 |
| 2 | $110 | $60 |
| 3 | $120 | $75 |
| 4 | $135 | $100 |
| 5 | $150 | $150 |

| Outcome | Steady fund | Volatile fund |
|---|---:|---:|
| Contributed | $5,000 | $5,000 |
| Shares accumulated | 41.4983 | 56.6667 |
| Ending value (approx.) | $6,224.75 | $8,500.00 |
| Simple return | 24.49% | 70.00% |

Both funds gained 50% from first to last price. The volatile fund produced greater investor wealth because more shares were purchased at lower prices before recovery.

However, this example deliberately assumes equal ending prices and a successful recovery. Real investments are not guaranteed to recover. An early crash may benefit an accumulating investor; a late crash can damage a large portfolio shortly before money is needed. Higher volatility alone is neither a source of guaranteed return nor a reason to concentrate in QQC.

## 10. Portfolio decision

| Strategy | VFV | VDY | QQC | Trade-off |
|---|---:|---:|---:|---|
| US core only | 100% | 0% | 0% | Simple; US large-cap concentration |
| Canadian dividends only | 0% | 100% | 0% | Financial and energy concentration |
| Nasdaq growth only | 0% | 0% | 100% | Higher growth-style concentration |
| Core-focused | 60% | 20% | 20% | Broader core with modest tilts |
| Proposed three-way allocation | 50% | 25% | 25% | Balanced among these exposures, still aggressive |
| Equal weight | 33.34% | 33.33% | 33.33% | No dominant fund, not equal underlying sector exposure |
| Aggressive growth tilt | 40% | 20% | 40% | Greater overlapping US growth exposure |

For a young investor with a multi-decade horizon, sufficient emergency savings and a high tolerance for equity risk, a three-way allocation is a defensible compromise. The 50/25/25 example emphasizes a broad US core while retaining Canadian dividend and Nasdaq growth tilts.

| Biweekly budget | VFV (50%) | VDY (25%) | QQC (25%) |
|---|---:|---:|---:|
| $500 | $250 | $125 | $125 |
| $1,000 | $500 | $250 | $250 |
| $2,000 | $1,000 | $500 | $500 |

At 26 deposits per year, $500 biweekly contributes approximately $13,000 annually. Some calendar years can contain 27 biweekly paydays.

This portfolio is 100% equities, not a conservative or fully globally diversified portfolio. VFV and QQC overlap substantially, while VDY is concentrated in two domestic sectors. Consider XEQT or VEQT for broader global equity exposure and simpler management, or an allocation including bonds or cash if the investment horizon or risk tolerance warrants it.

## 11. Investment policy checklist

- Invest a sustainable amount automatically every payday, rather than attempting to predict market bottoms.
- Keep emergency savings and money needed in the near term separate from equities.
- Address expensive debt and check available registered-account contribution room before funding accounts. Annual deposits may exceed new TFSA room; verify actual remaining room.
- Reinvest distributions if long-term accumulation is the objective.
- Review the allocation annually; direct new contributions toward underweight positions where practical and consider tax consequences before selling.
- Do not switch strategies solely because another ETF recently outperformed.
- Revisit the strategy if financial goals, time horizon, income stability or ability to tolerate losses change.

A severe market downturn can temporarily reduce a $100,000 equity portfolio to $50,000 or less. The appropriate allocation is one the investor can afford and realistically maintain through such conditions, not merely the one with the highest historical return.

## 12. Validation and future development

Before treating the results as decision-grade evidence:

1. Audit contribution dates and amounts, including initial deposits and the terminal valuation date.
2. Confirm adjusted prices and distributions are never double-counted. Verify split handling and dividend eligibility in cash mode.
3. Cross-check XIRR and TWR against independent calculations and deterministic synthetic tests.
4. Ensure drawdowns and volatility use cash-flow-adjusted returns, not raw growing account balances.
5. Check that charts and summary tables share the identical final observation; the January growth chart and comparison table appear to have slightly different visual endpoints.
6. Rerun VFV and VDY without QQC to extend historical coverage; confirm available data rather than assuming inception coverage.
7. Add end-date sensitivity analysis with fixed start date and identical contribution settings.
8. Show rolling window count, date range and non-overlapping samples where possible.
9. Test longer benchmark histories covering the dot-com bust, 2008 crisis and other market regimes. Clearly distinguish index proxies from actual ETF returns, and account for currency, dividends and fees consistently.
10. Backtest the proposed portfolios under no rebalancing, contribution-based rebalancing and annual rebalancing. Include taxes and costs where relevant.
11. Add inflation-adjusted results, downside scenarios and comparisons of lump sum versus recurring contributions. For a fair comparison, distinguish investing cash already available from investing future paychecks.

Potential tests include zero-growth constant prices, identical outcomes for a standalone ETF and its 100% custom portfolio, conserved capital during cost-free rebalancing, identical common-period contributions and a drawdown that remains unchanged by external deposits.

## Conclusion

This research does not establish a permanent winner among VFV, VDY and QQC. QQC led the common-period experiment ending January 2026, while VDY led the later comparison and exhibited stronger measured risk-adjusted returns. VFV remains a broad US core despite trailing in these particular samples.

The strongest lesson is not to maximize returns in hindsight. It is to choose an affordable, diversified investment strategy consistent with one's goals, automate contributions, and remain disciplined through changing market conditions.

The simulator should be used to understand trade-offs and stress-test decisions, not to predict the next winning ETF. Historical performance does not guarantee future results.

---

**Evidence and limitations:** All reported numerical backtest results are transcribed from the user's application screenshots in the November 25, 2026 conversation. They have not been independently reproduced from historical market data or audited against the Python implementation. General financial explanations and the hypothetical example are analytical context, not additional empirical findings. Portfolio weights are illustrative, not personalized financial advice. The screenshot-derived results may change as historical data is corrected or application calculations are improved.

import unittest

import pandas as pd

from finance import portfolio_allocations_valid, risk_metrics, simulate_portfolio, simulate_single, trading_schedule


def frame(values, dividends=None):
    index = pd.date_range("2020-01-02", periods=len(values), freq="B")
    return pd.DataFrame({"Close": values, "Adj Close": values, "Dividends": dividends or [0.0] * len(values)}, index=index)


class FinanceTests(unittest.TestCase):
    def test_schedule_moves_weekend_to_next_trading_day(self):
        index = pd.DatetimeIndex(["2020-01-06", "2020-01-20"])
        self.assertEqual(list(trading_schedule(index, pd.Timestamp("2020-01-04"), pd.Timestamp("2020-01-20"))), list(index))

    def test_constant_price_has_zero_growth(self):
        data = frame([100.0] * 40); result = simulate_single("VFV", data, data.index[0], data.index[-1], 500, 0, "price")
        self.assertAlmostEqual(result.growth, 0.0, places=7)

    def test_cash_dividends_are_separate(self):
        data = frame([100.0] * 40, [0.0] * 10 + [1.0] + [0.0] * 29); result = simulate_single("VDY", data, data.index[0], data.index[-1], 500, 0, "cash")
        self.assertGreaterEqual(result.cash_received, 0.0); self.assertAlmostEqual(result.final_value + result.cash_received - result.total_contributed, result.growth)

    def test_allocation_validation(self):
        self.assertTrue(portfolio_allocations_valid({"VFV": 0.5, "VDY": 0.3, "QQC": 0.2})); self.assertFalse(portfolio_allocations_valid({"VFV": 0.5, "VDY": 0.3, "QQC": 0.3}))

    def test_100_percent_portfolio_matches_single(self):
        data = frame([100 + i for i in range(50)]); single = simulate_single("VFV", data, data.index[0], data.index[-1], 500, 0, "price"); portfolio = simulate_portfolio("100% VFV", {"VFV": 1.0, "VDY": 0.0, "QQC": 0.0}, {"VFV": data}, data.index[0], data.index[-1], 500, 0, "price")
        self.assertAlmostEqual(single.final_value, portfolio.final_value, places=7); self.assertAlmostEqual(single.total_contributed, portfolio.total_contributed, places=7)

    def test_drawdown_is_negative_and_has_dates(self):
        data = frame([100, 110, 80, 90, 120] + [120] * 35); result = simulate_single("VFV", data, data.index[0], data.index[-1], 500, 0, "price"); metrics = risk_metrics(result)
        self.assertLessEqual(metrics["max_drawdown"], 0); self.assertIn("drawdown_start", metrics)


if __name__ == "__main__": unittest.main()

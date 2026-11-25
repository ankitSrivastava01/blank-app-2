import unittest

import pandas as pd

from stock_health import stock_health, technical_indicators


class StockHealthTests(unittest.TestCase):
    @staticmethod
    def history(values):
        return pd.DataFrame({"Close": values}, index=pd.date_range("2025-01-01", periods=len(values)))

    @staticmethod
    def company():
        return {"returnOnEquity": 0.20, "revenueGrowth": 0.20, "earningsGrowth": 0.25,
                "profitMargins": 0.20, "trailingPE": 15, "priceToBook": 2,
                "debtToEquity": 30, "currentRatio": 2, "beta": 0.8}

    def test_flat_price_has_neutral_technicals_and_equal_factor_weights(self):
        result = stock_health(self.company(), self.history([100] * 220))
        self.assertEqual(result["available"], 12)
        self.assertEqual(result["factors"]["Momentum"], 50)
        self.assertEqual(result["overall"], 87.5)
        self.assertEqual(result["technical"]["rsi14"], 50)

    def test_missing_data_does_not_become_score(self):
        result = stock_health({}, self.history([100] * 220))
        self.assertEqual(result["available"], 3)
        self.assertIsNone(result["overall"])
        self.assertIsNone(stock_health(self.company(), pd.DataFrame())["overall"])

    def test_financial_sector_excludes_leverage_and_liquidity(self):
        info = dict(self.company(), sector="Financial Services", debtToEquity=9999, currentRatio=0)
        result = stock_health(info, self.history([100] * 220))
        self.assertEqual(result["applicable"], 10)
        self.assertEqual(result["factors"]["Risk"], 100)

    def test_negative_earnings_and_equity_are_not_rewarded(self):
        info = dict(self.company(), trailingPE=-5, priceToBook=-3, debtToEquity=-100)
        result = stock_health(info, self.history([100] * 220))
        self.assertEqual(result["factors"]["Valuation"], 0)
        self.assertEqual(next(c["Points"] for c in result["checks"] if c["Indicator"] == "Debt/equity (x)"), 0)
        self.assertTrue(0 <= result["overall"] <= 100)

    def test_wilder_rsi_handles_rising_falling_and_short_history(self):
        self.assertEqual(technical_indicators(self.history(range(1, 31)))["rsi14"], 100)
        self.assertEqual(technical_indicators(self.history(range(30, 0, -1)))["rsi14"], 0)
        short = technical_indicators(self.history([100] * 10))
        self.assertIsNone(short["rsi14"])
        self.assertIsNone(short["sma50"])
        self.assertIsNone(short["signal"])

    def test_moving_averages_require_full_window(self):
        technical = technical_indicators(self.history(range(1, 201)))
        self.assertEqual(technical["sma200"], 100.5)
        self.assertEqual(technical["sma50"], 175.5)
        self.assertIsNotNone(technical["signal"])


if __name__ == "__main__":
    unittest.main()

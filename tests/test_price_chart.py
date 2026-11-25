import unittest

import pandas as pd

from price_chart import prepare_price_history


class PriceChartTests(unittest.TestCase):
    def test_averages_use_history_before_display_window(self):
        history = pd.DataFrame({"Close": [100.0] * 250}, index=pd.bdate_range("2025-01-01", periods=250))
        frame = prepare_price_history(history, "1W")
        self.assertLess(len(frame), 10)
        self.assertTrue(frame["200-day average"].eq(100).all())

    def test_invalid_prices_are_excluded(self):
        history = pd.DataFrame({"Close": [100, None, -1, float("inf"), 110]}, index=pd.date_range("2026-01-01", periods=5))
        frame = prepare_price_history(history, "1Y")
        self.assertEqual(frame["Close"].tolist(), [100, 110])
        self.assertTrue(frame["50-day average"].isna().all())


if __name__ == "__main__":
    unittest.main()

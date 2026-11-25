import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from market_data import load_stock_details, load_stock_page, period_return, quote_row, screen_query
from indicators import company_indicators
from stock_explorer import yahoo_error_reason


class MarketDataTests(unittest.TestCase):
    def test_yahoo_error_reason_only_reports_known_descriptions(self):
        response = Mock()
        response.json.return_value = {"finance": {"error": {"description": "Invalid Crumb"}}}
        self.assertEqual(yahoo_error_reason(response), "invalid crumb")
        response.json.return_value = {"finance": {"error": {"description": "User is unable to access this feature"}}}
        self.assertEqual(yahoo_error_reason(response), "access denied by Yahoo")
        response.json.return_value = {"finance": {"error": {"description": "sensitive unknown text"}}}
        self.assertEqual(yahoo_error_reason(response), "unknown")
        self.assertEqual(yahoo_error_reason(None), "unknown")

    def setUp(self):
        load_stock_page.clear()
        load_stock_details.clear()

    def test_price_filters_reach_provider_in_both_markets(self):
        for country, region in [("India", "in"), ("USA", "us")]:
            for band, operator, operands in [
                ("Below 10", "LT", ["intradayprice", 10]),
                ("10 - 100", "BTWN", ["intradayprice", 10, 100]),
                ("100 - 500", "BTWN", ["intradayprice", 100, 500]),
                ("Above 10000", "GT", ["intradayprice", 10000]),
            ]:
                query = screen_query(country, band).to_dict()
                self.assertIn({"operator": "EQ", "operands": ["region", region]}, query["operands"])
                self.assertIn({"operator": operator, "operands": operands}, query["operands"])

    def test_all_sector_cap_and_valuation_queries_are_valid(self):
        for country in ["India", "USA"]:
            for cap in ["All", "Large Cap", "Mid Cap", "Small Cap"]:
                for valuation in ["All", "Value", "Growth", "Defensive"]:
                    self.assertEqual(screen_query(country, "All", "Technology", cap, valuation).to_dict()["operator"], "AND")

    @patch("market_data.yf.screen")
    def test_pagination_and_missing_values(self, screen):
        screen.return_value = {"total": 230, "quotes": [{"symbol": "TEST", "regularMarketPrice": 8.5}]}
        rows, total, _ = load_stock_page("USA", "Below 10", page=1)
        self.assertEqual(screen.call_args.kwargs["offset"], 100)
        self.assertEqual(screen.call_args.kwargs["size"], 100)
        self.assertEqual(total, 230)
        self.assertEqual(rows[0]["Price"], 8.5)
        self.assertIsNone(rows[0]["P/E"])
        self.assertEqual(rows[0]["Currency"], "USD")

    @patch("market_data.yf.screen", return_value={})
    def test_malformed_response_is_error_not_empty_market(self, screen):
        with self.assertRaises(ValueError):
            load_stock_page("India")

    @patch("market_data.yf.Ticker")
    def test_history_survives_fundamentals_failure(self, ticker):
        ticker.return_value.get_info.side_effect = RuntimeError("rate limited")
        ticker.return_value.history.return_value = pd.DataFrame({"Close": [10, 11]})
        info, history, errors = load_stock_details("TEST")
        self.assertEqual(info, {})
        self.assertFalse(history.empty)
        self.assertTrue(errors)

    def test_returns_use_trading_sessions(self):
        history = pd.DataFrame({"Close": [100, 102, 104, 106, 108, 110]})
        self.assertAlmostEqual(period_return(history, 5), 10)
        self.assertIsNone(period_return(history, 21))
        self.assertIsNone(period_return(pd.DataFrame(), 1))

    def test_indicator_units_zero_and_missing_values(self):
        indicators = company_indicators({"returnOnEquity": 0.18, "returnOnAssets": 0.07,
                                         "debtToEquity": 150, "profitMargins": -0.02,
                                         "earningsGrowth": 0, "trailingAnnualDividendYield": 0.015})
        self.assertEqual(len(indicators), 12)
        values = {label: value for label, value, *_ in indicators}
        self.assertAlmostEqual(values["Return on equity"], 18)
        self.assertAlmostEqual(values["Debt / equity"], 1.5)
        self.assertAlmostEqual(values["Dividend yield (trailing)"], 1.5)
        self.assertAlmostEqual(values["Net profit margin"], -2)
        self.assertEqual(values["Earnings growth (YoY)"], 0)
        self.assertIsNone(values["Beta"])


class AppTests(unittest.TestCase):
    def setUp(self):
        self.page_mock = patch("stock_explorer.load_stock_page", side_effect=self.page).start()
        self.details_mock = patch("stock_explorer.load_stock_details", return_value=(
            {"currency": "USD", "currentPrice": 8.5},
            pd.DataFrame({"Close": [7, 8.5]}, index=pd.date_range("2026-01-01", periods=2, name="Date")), []
        )).start()
        self.addCleanup(patch.stopall)

    @staticmethod
    def page(country, price, sector, stock_type, valuation, page):
        symbol = "TEST.NS" if country == "India" else "TEST"
        return [quote_row({"symbol": symbol, "regularMarketPrice": 8.5}, country)], 250, "2026-10-31T00:00:00+00:00"

    def test_currencies_pagination_and_filter_reset(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=15).run()
        self.assertFalse(app.exception)
        for country, currency in [("India", "\u20b9"), ("USA", "$"), ("All", "\u20b9 / $")]:
            app.selectbox(key="stock_country").set_value(country).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.selectbox(key="stock_price_range").options[1], f"Below {currency}10")
        next(b for b in app.button if b.label == "Next page").click().run()
        self.assertEqual(app.session_state.stock_page, 1)
        app.selectbox(key="stock_price_range").set_value("Below 10").run()
        self.assertEqual(app.session_state.stock_page, 0)
        self.assertFalse(app.exception)

    def test_provider_failure_shows_error_without_loading_details(self):
        self.page_mock.side_effect = RuntimeError("offline")
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=15).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 2)
        self.details_mock.assert_not_called()
        self.assertEqual(len(app.text_input), 0)

    def test_details_load_only_after_selection_and_clear_on_filter(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=15).run()
        self.details_mock.assert_not_called()
        self.assertEqual(len(app.metric), 0)
        self.assertIsNone(app.selectbox(key="stock_selection").value)
        app.selectbox(key="stock_selection").set_value("TEST").run()
        self.assertFalse(app.exception)
        self.details_mock.assert_called_once_with("TEST")
        self.assertTrue(any(m.label == "1D" for m in app.metric))
        self.assertTrue(any(h.value == "AI Briefing" for h in app.subheader))
        self.details_mock.reset_mock()
        app.selectbox(key="stock_price_range").set_value("Below 10").run()
        self.assertFalse(app.exception)
        self.details_mock.assert_not_called()
        self.assertEqual(len(app.metric), 0)

    def test_selection_clears_when_page_changes(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=15).run()
        app.selectbox(key="stock_selection").set_value("TEST").run()
        self.details_mock.assert_called_once_with("TEST")
        self.details_mock.reset_mock()
        next(b for b in app.button if b.label == "Next page").click().run()
        self.assertFalse(app.exception)
        self.assertIsNone(app.selectbox(key="stock_selection").value)
        self.details_mock.assert_not_called()

    def test_one_health_score_replaces_indicator_cards_without_news(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=15).run()
        app.selectbox(key="stock_selection").set_value("TEST").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.tabs), 12)
        self.assertEqual(app.tabs[0].label, "1. Company Overview")
        self.assertEqual(app.tabs[9].label, "10. AI Briefing")
        self.assertEqual(app.tabs[10].label, "11. Company Size & Workforce")
        self.assertEqual(app.tabs[11].label, "12. Announcements")
        labels = {m.label for m in app.metric}
        self.assertIn("Stock Health Score", labels)
        self.assertFalse({i[0] for i in company_indicators({})} & labels)
        self.assertFalse(any("news" in h.value.lower() for h in app.subheader))
        self.assertEqual(next(m.value for m in app.metric if m.label == "Stock Health Score"), "Insufficient data")

    def test_dropdown_only_contains_prices_in_selected_range(self):
        def mixed_prices(country, *args):
            return [quote_row({"symbol": symbol, "regularMarketPrice": price}, country)
                    for symbol, price in [("LOW", 5), ("MATCH", 50), ("HIGH", 900)]], 3, "2026-10-31T00:00:00+00:00"
        self.page_mock.side_effect = mixed_prices
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=15).run()
        app.selectbox(key="stock_country").set_value("USA").run()
        app.selectbox(key="stock_price_range").set_value("10 - 100").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="stock_selection").options, ["MATCH (MATCH) — $50.00"])
        self.assertEqual(len(app.dataframe), 0)
        self.assertEqual(len(app.text_input), 0)
        self.details_mock.assert_not_called()

    @patch("stock_explorer.load_company_announcements", return_value={"records": [
        {"Headline": "Example filing", "Published": "2026-10-30", "Source": "SEC EDGAR", "Source URL": "https://www.sec.gov/example.htm"}], "error": None, "note": "Recent regulatory filings."})
    def test_announcements_load_only_when_enabled(self, announcements):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=15).run()
        app.selectbox(key="stock_selection").set_value("TEST").run()
        announcements.assert_not_called()
        app.toggle[0].set_value(True).run()
        self.assertFalse(app.exception)
        announcements.assert_called_once_with("TEST", "TEST", "USA")
        self.assertTrue(any("Example filing" in frame.value.to_string() for frame in app.dataframe))


if __name__ == "__main__":
    unittest.main()

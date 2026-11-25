import unittest
from unittest.mock import Mock, patch

from company_growth import annual_observations, growth_percent, sec_growth_rows, indian_company_growth


class CompanyGrowthTests(unittest.TestCase):
    @staticmethod
    def annual(start, end, value, filed):
        return {"start": start, "end": end, "val": value, "filed": filed, "form": "10-K"}

    def test_growth_handles_losses_and_zero_bases(self):
        self.assertEqual(growth_percent(120, 100), "+20.00%")
        self.assertEqual(growth_percent(80, 100), "-20.00%")
        self.assertIn("Not meaningful", growth_percent(10, -20))
        self.assertIn("Not meaningful", growth_percent(10, 0))

    def test_annual_periods_exclude_quarters_and_pick_latest_restatement(self):
        facts = [self.annual("2024-01-01", "2024-12-31", 100, "2025-02-01"),
                 self.annual("2024-01-01", "2024-12-31", 110, "2026-02-01"),
                 self.annual("2025-01-01", "2025-03-31", 40, "2025-05-01")]
        rows = annual_observations(facts)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["val"], 110)

    def test_same_concept_and_currency_are_compared(self):
        facts = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            self.annual("2024-01-01", "2024-12-31", 100, "2025-02-01"),
            self.annual("2025-01-01", "2025-12-31", 120, "2026-02-01")],
            "EUR": [self.annual("2025-01-01", "2025-12-31", 900, "2026-02-01")]}}}}}
        rows = sec_growth_rows(facts, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["YoY growth"], "+20.00%")
        self.assertEqual(rows[0]["Current"], "120 USD")

    def test_nonconsecutive_years_do_not_become_yoy_growth(self):
        data = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            self.annual("2023-01-01", "2023-12-31", 100, "2024-02-01"),
            self.annual("2025-01-01", "2025-12-31", 200, "2026-02-01")]}}}}}
        self.assertEqual(sec_growth_rows(data, 1), [])

    @patch("company_growth.get")
    def test_tcs_report_handles_html_word_spacing(self, get):
        get.return_value.text = "<p>quarter ending September 30, 2026</p><p>Q2 Revenue at $7,642 Mn ; Growth +0.2% QoQ , +2.4% YoY in USD</p>"
        rows = indian_company_growth("TCS.NS", "https://www.tcs.com")
        self.assertEqual(rows[0]["YoY growth"], "+2.40%")
        self.assertEqual(rows[0]["Current"], "7,642 USD million")


if __name__ == "__main__":
    unittest.main()

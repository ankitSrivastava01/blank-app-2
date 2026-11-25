import unittest

import pandas as pd

from company_factors import company_factor_rows


class CompanyFactorsTests(unittest.TestCase):
    def test_all_ten_factors_handle_missing_provider_data(self):
        rows = company_factor_rows({}, pd.DataFrame(), "INR")
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row["Company readings"] for row in rows))
        self.assertIn("Unavailable", rows[0]["Company readings"])
        self.assertIn("Disabled", rows[-1]["Company readings"])

    def test_units_zero_values_and_ownership_are_explicit(self):
        rows = company_factor_rows({"financialCurrency": "USD", "totalRevenue": 1000,
                                    "revenueGrowth": 0.12, "earningsGrowth": 0,
                                    "trailingEps": 2, "debtToEquity": 150,
                                    "heldPercentInstitutions": 0.25}, pd.DataFrame(), "INR")
        self.assertIn("1,000.00 USD", rows[0]["Company readings"])
        self.assertIn("2.00 INR", rows[0]["Company readings"])
        self.assertIn("12.00%", rows[0]["Company readings"])
        self.assertIn("0.00%", rows[0]["Company readings"])
        self.assertIn("1.50x", rows[3]["Company readings"])
        self.assertIn("25.00%", rows[7]["Company readings"])
        self.assertIn("not buying or selling flows", rows[7]["How to read"])

    def test_technicals_use_company_history(self):
        rows = company_factor_rows({}, pd.DataFrame({"Close": [100.0] * 220}), "USD")
        self.assertIn("SMA200: 100.00 USD", rows[8]["Company readings"])
        self.assertIn("RSI (14): 50.00", rows[8]["Company readings"])


if __name__ == "__main__":
    unittest.main()

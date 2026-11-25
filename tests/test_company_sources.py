import unittest
from unittest.mock import Mock, patch

from company_sources import (entity_records, load_company_enrichment, official_workforce,
                             parse_infosys_report, parse_tcs_report, wikidata_company)


class CompanySourceTests(unittest.TestCase):
    def setUp(self):
        load_company_enrichment.clear()

    def test_official_tcs_values_and_period(self):
        rows = parse_tcs_report("<p>quarter ending September 30, 2026</p><p>Workforce strength: 598,056; LTM Attrition (IT Services): 13.3%</p>")
        self.assertEqual(rows[0]["Value"], "598,056")
        self.assertEqual(rows[1]["Value"], "13.3%")
        self.assertEqual(rows[1]["Period / as of"], "2026-09-30")
        with self.assertRaises(ValueError):
            parse_tcs_report("Workforce strength: 100 LTM Attrition (IT Services): 15%")

    def test_infosys_table_checks_subtotals_and_units(self):
        text = """Employee Metrics
Sep 30, 2026 Jun 30, 2026 Sep 30, 2025
332,542 328,062 331,991
314,508 310,039 314,500
18,034 18,023 17,491
12.7% 13.0% 14.3%
39.8% 39.6% 39.5%
Voluntary Attrition % (LTM - IT Services)
Total employees
Cash Metrics"""
        rows = parse_infosys_report(text)
        self.assertEqual(rows[0]["Value"], "332,542")
        self.assertEqual(rows[3]["Value"], "12.7%")
        self.assertEqual(rows[1]["Period / as of"], "2026-06-30")
        with self.assertRaises(ValueError):
            parse_infosys_report(text.replace("314,508", "10"))

    @patch("company_sources.get")
    def test_unmatched_company_has_no_official_report_fetch(self, get):
        self.assertEqual(official_workforce("TCS", "https://other-company.com"), [])
        self.assertEqual(official_workforce("TCS.NS", "https://another.com"), [])
        get.assert_not_called()

    @patch("company_sources.get")
    def test_wikidata_requires_exact_company_website(self, get):
        get.return_value.json.return_value = {"results": {"bindings": [
            {"company": {"value": "http://www.wikidata.org/entity/Q1"},
             "website": {"value": "https://example.com.evil.invalid"}}]}}
        self.assertEqual(wikidata_company("TEST", "https://example.com"), [])
        self.assertEqual(get.call_count, 1)

    @patch("company_sources.get")
    def test_ambiguous_wikidata_identity_is_not_used(self, get):
        get.return_value.json.return_value = {"results": {"bindings": [
            {"company": {"value": f"http://www.wikidata.org/entity/Q{i}"},
             "website": {"value": "https://example.com"}} for i in [1, 2]]}}
        self.assertEqual(wikidata_company("TEST", "https://example.com"), [])

    def test_employee_claims_require_dates_and_exclude_scoped_or_deprecated(self):
        def claim(amount, year=None, **kwargs):
            result = {"mainsnak": {"datavalue": {"value": {"amount": str(amount), "unit": "1"}}}, **kwargs}
            if year:
                result["qualifiers"] = {"P585": [{"datavalue": {"value": {"time": f"+{year}-00-00T00:00:00Z", "precision": 9}}}]}
            return result
        scoped = claim(5, 2025)
        scoped["qualifiers"]["P518"] = [{}]
        rows = entity_records({"claims": {"P1128": [claim(100, 2024), claim(999), claim(50, 2025, rank="deprecated"), scoped]}}, "Q1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Value"], "100")
        self.assertEqual(rows[0]["Period / as of"], "2024")

    @patch("company_sources.official_workforce", side_effect=RuntimeError("offline"))
    @patch("company_sources.wikidata_company", return_value=[{"Detail": "Historical employee count", "Value": "100"}])
    def test_one_failed_source_does_not_discard_another(self, wikidata, official):
        result = load_company_enrichment("TEST", "https://example.com")
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(len(result["notices"]), 1)


if __name__ == "__main__":
    unittest.main()

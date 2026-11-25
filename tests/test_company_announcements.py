import unittest
from unittest.mock import patch

from company_announcements import load_company_announcements, parse_nse_announcements, sec_filing_rows


class AnnouncementTests(unittest.TestCase):
    def setUp(self):
        load_company_announcements.clear()

    @staticmethod
    def item(name, link="https://nsearchives.nseindia.com/corporate/example.pdf", date="31-Oct-2026 09:30:00"):
        return f"<item><title>{name}</title><link>{link}</link><description>Summary |SUBJECT: Financial Results</description><pubDate>{date}</pubDate></item>"

    def test_matches_full_name_and_legal_suffix_not_substrings(self):
        xml = ("<rss><channel>" + self.item("Example Limited") + self.item("Example Services Limited") + "</channel></rss>").encode()
        rows = parse_nse_announcements(xml, "Example Ltd.")
        self.assertEqual(len(rows), 1)
        self.assertIn("Financial Results", rows[0]["Headline"])
        self.assertIn("IST", rows[0]["Published"])

    def test_links_are_validated_and_duplicates_removed(self):
        xml = ("<rss><channel>" + self.item("Example Ltd") * 2 + self.item("Example Ltd", "https://evil.invalid/test") + "</channel></rss>").encode()
        self.assertEqual(len(parse_nse_announcements(xml, "Example Limited")), 1)

    def test_non_feed_and_entities_are_rejected(self):
        for xml in [b"<html>error</html>", b'<!DOCTYPE rss [<!ENTITY x "bad">]><rss/>']:
            with self.assertRaises(ValueError):
                parse_nse_announcements(xml, "Example")

    def test_sec_reports_are_deduplicated_and_company_verified(self):
        recent = {"form": ["8-K", "8-K", "4"], "accessionNumber": ["0000320193-26-000001"] * 3,
                  "primaryDocument": ["report.htm"] * 3, "filingDate": ["2026-10-30"] * 3}
        data = {"cik": 320193, "filings": {"recent": recent}}
        rows = sec_filing_rows(data, 320193)
        self.assertEqual(len(rows), 1)
        self.assertIn("320193/000032019326000001/report.htm", rows[0]["Source URL"])
        with self.assertRaises(ValueError):
            sec_filing_rows(data, 1)

    @patch("company_announcements.nse_feed", side_effect=RuntimeError("offline"))
    def test_provider_failure_is_explicit(self, feed):
        result = load_company_announcements("TEST.NS", "Example Ltd", "India")
        self.assertTrue(result["error"])
        self.assertEqual(result["records"], [])

    @patch("company_announcements.nse_feed")
    def test_bse_listing_does_not_match_an_nse_company_by_guess(self, feed):
        result = load_company_announcements("123456.BO", "Example Ltd", "India")
        self.assertIn("BSE", result["note"])
        feed.assert_not_called()


if __name__ == "__main__":
    unittest.main()

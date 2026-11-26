"""Regression checks for outage fallbacks, workspace isolation and indicators."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import investo_data as data
import investo_store as store
from investo_analysis import alert_status, position_cost, sentiment, technicals


class StorageTests(unittest.TestCase):
    def setUp(self):
        temp = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.dict(os.environ, {"INVESTO_DB_PATH": str(Path(temp) / "data.sqlite3")}))

    def test_fallback_retains_source_and_rejects_expired_snapshots(self):
        def down():
            raise ConnectionError("Provider unavailable")

        providers = [("Primary", down), ("Secondary", lambda: {"price": 100})]
        current = data.last_good("quote", providers, 7)
        self.assertEqual(current["source"], "Secondary")
        self.assertFalse(current["stale"])
        fallback = data.last_good("quote", providers[:1], 7)
        self.assertEqual(fallback, dict(current, stale=True))
        with store.database() as db:
            expiry = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
            db.execute("UPDATE snapshots SET fetched=? WHERE name='quote'", (expiry,))
        self.assertIsNone(data.last_good("quote", providers[:1], 7)["data"])

    def test_workspace_recovers_purchases_and_prevents_cross_workspace_deletes(self):
        code = store.create_workspace()
        owner = store.unlock_workspace(code)
        other = store.unlock_workspace(store.create_workspace())
        self.assertNotEqual(owner, other)
        store.add_purchase(owner, "500325.BO", "RELIANCE.BO", "Reliance", 2, 10001, "2026-01-02")
        store.add_purchase(owner, "500325.BO", "RELIANCE.BO", "Reliance", 1, 20000, "2026-01-03")
        lots = store.purchases(owner)
        self.assertEqual(position_cost(lots), (3, 400.02))
        store.remove_purchase(other, lots[0]["id"])
        self.assertEqual(store.purchases(other), [])
        self.assertEqual(store.purchases(store.unlock_workspace(code)), lots)
        store.save_watch(owner, "500325.BO", "RELIANCE.BO", "Reliance", "At or above", 200)
        store.save_watch(owner, "500325.BO", "RELIANCE.BO", "Reliance", "At or below", 200)
        self.assertEqual(len(store.watchlist(owner)), 1)
        self.assertEqual(store.watchlist(owner)[0]["direction"], "At or below")
        self.assertEqual(store.watchlist(other), [])


class ResearchTests(unittest.TestCase):
    def test_indicators_respect_warmup_and_flat_market(self):
        frame = technicals(pd.DataFrame({"Close": [100.0] * 205}))
        self.assertTrue(pd.isna(frame.iloc[13]["RSI 14"]))
        self.assertEqual(frame.iloc[14]["RSI 14"], 50)
        self.assertEqual(frame.iloc[-1]["SMA 200"], 100)
        self.assertEqual(frame.iloc[-1]["Histogram"], 0)
        self.assertEqual(frame.iloc[-1]["Upper band"], 100)

    def test_threshold_waits_for_usable_close_and_sentiment_handles_mixed_headlines(self):
        self.assertEqual(alert_status("At or above", 100, 101, False), "Awaiting recent close")
        self.assertEqual(alert_status("At or below", 100, 100, True), "Target met")
        self.assertEqual(sentiment("Profit rises as shares fall"), "Neutral")
        self.assertEqual(sentiment("Company wins contract"), "Positive")
        self.assertEqual(sentiment("Company misses estimates"), "Negative")


if __name__ == "__main__":
    unittest.main()

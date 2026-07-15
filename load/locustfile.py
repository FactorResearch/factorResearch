"""Production-proof workloads. Run only against an approved staging target."""

from __future__ import annotations

import os
import random

from locust import HttpUser, between, task


TICKERS = tuple(filter(None, os.environ.get("LOAD_TICKERS", "AAPL,MSFT,NVDA,META,GOOGL").split(",")))
SAME_TICKER = os.environ.get("LOAD_SAME_TICKER", "AAPL")


class BrowsingUser(HttpUser):
    weight = 6
    wait_time = between(0.4, 1.8)

    @task(5)
    def screener(self):
        self.client.get("/screener/us", name="GET /screener/us")

    @task(2)
    def privacy(self):
        self.client.get("/privacy", name="GET /privacy")

    @task(1)
    def terms(self):
        self.client.get("/terms", name="GET /terms")


class AnalysisReader(HttpUser):
    weight = 3
    wait_time = between(1, 3)

    @task
    def company_analysis(self):
        ticker = random.choice(TICKERS)
        self.client.get(f"/analyze/{ticker}", name="GET /analyze/[ticker]")


class SameTickerUser(HttpUser):
    weight = 1
    wait_time = between(0.2, 0.8)

    @task
    def same_ticker(self):
        self.client.get(f"/analyze/{SAME_TICKER}", name="GET /analyze/[same-ticker]")

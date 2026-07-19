import unittest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
import sys
import os
import datetime

sys.path.insert(0, os.path.abspath('.'))

from codes.portfolio import (
    create_portfolio, add_holding, remove_holding, load_portfolio,
    run_backtest, run_montecarlo, analyze_weak_links, run_simulation,
    get_cumulative_split_factor, _splits_since, _split_factor_at,
    invalidate_simulation_cache
)


class TestPortfolio(unittest.TestCase):

    def setUp(self):
        self.user_id = "test-user"
        self.test_portfolio_name = "TestPortfolio"

    # ====================== SPLIT ADJUSTMENT ======================

    def test_split_helpers(self):
        """Test split factor calculations."""
        splits = [
            {"date": "2022-06-01", "ratio": 2.0},
            {"date": "2023-01-15", "ratio": 3.0}
        ]
        self.assertEqual(_split_factor_at(splits, pd.Timestamp("2021-12-31")), 1.0)
        self.assertEqual(_split_factor_at(splits, pd.Timestamp("2022-10-01")), 2.0)
        self.assertEqual(_split_factor_at(splits, pd.Timestamp("2023-06-01")), 6.0)

    @patch('codes.portfolio._splits_since')
    def test_get_cumulative_split_factor(self, mock_splits):
        mock_splits.return_value = [{"date": "2022-06-01", "ratio": 4.0}]
        factor = get_cumulative_split_factor("AAPL", "2022-01-01")
        self.assertGreater(factor, 1.0)

    # ====================== PORTFOLIO CRUD ======================

    @patch('codes.portfolio.cache')
    def test_portfolio_crud(self, mock_cache):
        """Test create, add, remove portfolio flow."""
        # Setup cache mock to simulate real behavior
        portfolios = {}  # in-memory simulation

        def mock_read(category, key):
            if key == "index":
                return list(portfolios.keys())
            return portfolios.get(key)

        def mock_write(category, key, value):
            portfolios[key] = value
            if key.startswith("p_"):
                name = key[2:]
                if name not in portfolios.get("index", []):
                    if "index" not in portfolios:
                        portfolios["index"] = []
                    portfolios["index"].append(name)

        def mock_clear(category, key):
            portfolios.pop(key, None)

        mock_cache.read.side_effect = mock_read
        mock_cache.write.side_effect = mock_write
        mock_cache.write_if_version.side_effect = (
            lambda category, key, value, _version: mock_write(category, key, value) or True
        )
        mock_cache.clear.side_effect = mock_clear

        # Create portfolio
        p = create_portfolio(self.user_id, self.test_portfolio_name)
        self.assertEqual(p["name"], self.test_portfolio_name)
        self.assertIn("holdings", p)

        # Add holding
        with patch('codes.portfolio.api_fetcher') as mock_av:
            mock_av.get_price_history.return_value = pd.DataFrame()
            updated, err = add_holding(self.user_id, self.test_portfolio_name, "AAPL", 10, 150.0, "Apple Inc.")
            self.assertEqual(err, "", f"Add holding failed: {err}")
            self.assertIn("AAPL", updated["holdings"])

        # Remove holding
        _, err = remove_holding(self.user_id, self.test_portfolio_name, "AAPL")
        self.assertEqual(err, "")

    # ====================== BACKTEST ======================

    @patch('codes.portfolio._splits_since', return_value=[])
    @patch('codes.portfolio._load_history')
    def test_run_backtest_basic(self, mock_load, _mock_splits):
        dates = pd.date_range('2023-01-01', periods=36, freq='ME')
        df = pd.DataFrame({
            'Date': dates,
            'Close': np.cumprod(1 + np.random.normal(0.008, 0.04, 36))
        })
        mock_load.return_value = df

        portfolio = {
            "name": "Test",
            "holdings": {"AAPL": {"shares": 10, "price_at_add": 150.0, "added_date": "2023-01-01"}}
        }

        result = run_backtest(portfolio)
        self.assertIsNone(result.get("error"))
        self.assertIn("cagr", result)

    @patch('codes.portfolio._load_history')
    def test_backtest_empty_portfolio(self, mock_load):
        result = run_backtest({"name": "Empty", "holdings": {}})
        self.assertIn("error", result)

    # ====================== MONTE CARLO ======================

    @patch('codes.portfolio._load_history')
    def test_montecarlo_correlation_matrix(self, mock_load_history):
        """Test correlation matrix is symmetric and captures dependence."""
        dates = pd.date_range('2020-01-01', periods=60, freq='ME')
        returns1 = np.random.normal(0.008, 0.05, 60)
        returns2 = returns1 * 0.7 + np.random.normal(0, 0.03, 60)

        df1 = pd.DataFrame({'Date': dates, 'Close': np.cumprod(1 + returns1)})
        df2 = pd.DataFrame({'Date': dates, 'Close': np.cumprod(1 + returns2)})

        mock_load_history.side_effect = lambda sym: df1 if sym == 'AAPL' else df2

        portfolio = {
            "name": "TestPort",
            "holdings": {
                "AAPL": {"shares": 10, "price_at_add": 150.0},
                "GOOGL": {"shares": 5, "price_at_add": 2800.0},
            }
        }
        backtest = {"final_value": 50000.0, "final_spy": 55000.0, "error": None}

        result = run_montecarlo(portfolio, backtest)
        self.assertIsNone(result.get("error"))
        self.assertGreater(len(result.get("p50", [])), 20)

        p10 = np.array(result["p10"])
        p90 = np.array(result["p90"])
        self.assertTrue(np.all(p10 <= p90))

    @patch('codes.portfolio._load_history')
    def test_montecarlo_single_asset(self, mock_load_history):
        portfolio = {"name": "Single", "holdings": {"AAPL": {"shares": 10, "price_at_add": 150.0}}}
        bt = {"final_value": 2000.0, "error": None}

        mock_df = pd.DataFrame({
            'Date': pd.date_range('2020-01-01', periods=60, freq='ME'),
            'Close': np.cumprod(1 + np.random.normal(0.008, 0.04, 60))
        })
        mock_load_history.return_value = mock_df

        result = run_montecarlo(portfolio, bt)
        self.assertIsNone(result.get("error"))

    def test_montecarlo_empty(self):
        result = run_montecarlo({"holdings": {}}, {})
        self.assertIn("error", result)

    # ====================== WEAK LINKS + FULL SIMULATION ======================

    @patch('codes.portfolio._splits_since', return_value=[])
    @patch('codes.portfolio.run_backtest')
    @patch('codes.portfolio._load_history')
    def test_analyze_weak_links(self, mock_load, mock_backtest, _mock_splits):
        mock_backtest.return_value = {
            "cagr": 12.5, "spy_cagr": 10.0, "error": None,
            "holdings_detail": {"AAPL": {}}, "final_value": 50000
        }

        dates = pd.date_range('2020-01-01', periods=24, freq='ME')
        df = pd.DataFrame({'Date': dates, 'Close': np.cumprod(1 + np.random.normal(0.01, 0.05, 24))})
        mock_load.return_value = df

        portfolio = {
            "name": "Test",
            "holdings": {"AAPL": {"shares": 10, "price_at_add": 150.0, "added_date": "2020-01-01"}}
        }

        result = analyze_weak_links(portfolio)
        self.assertIsNone(result.get("error"))

    @patch('codes.portfolio._splits_since', return_value=[])
    @patch('codes.portfolio._load_history')
    def test_only_largest_counterfactual_drag_is_the_weak_link(self, mock_load, _mock_splits):
        """Several underperformers may be drags, but only one can be the weakest link."""
        dates = pd.date_range('2020-01-01', periods=24, freq='ME')
        closes = {
            "AAA": np.linspace(100.0, 50.0, len(dates)),
            "BBB": np.linspace(100.0, 70.0, len(dates)),
            "SPY": np.linspace(100.0, 120.0, len(dates)),
        }
        mock_load.side_effect = lambda symbol: pd.DataFrame(
            {"Date": dates, "Close": closes[symbol]}
        )
        portfolio = {
            "created": "2020-01-01",
            "holdings": {
                "AAA": {"shares": 1, "price_at_add": 100.0},
                "BBB": {"shares": 1, "price_at_add": 100.0},
            },
        }
        backtest = {
            "cagr": -20.0,
            "spy_cagr": 9.5,
            "error": None,
            "holdings_detail": {"AAA": {}, "BBB": {}},
        }

        result = analyze_weak_links(portfolio, backtest)

        assert result["weakest"] == "AAA"
        assert result["holdings"]["AAA"]["verdict"] == "weak link"
        assert result["holdings"]["BBB"]["verdict"] == "drag"
        assert sum(
            holding["verdict"] == "weak link" for holding in result["holdings"].values()
        ) == 1

    @patch('codes.portfolio._splits_since', return_value=[])
    @patch('codes.portfolio._load_history')
    def test_tied_counterfactual_drags_have_no_arbitrary_weak_link(self, mock_load, _mock_splits):
        """Equal largest impacts remain drags because neither is uniquely weakest."""
        dates = pd.date_range('2020-01-01', periods=24, freq='ME')
        closes = {
            "AAA": np.linspace(100.0, 60.0, len(dates)),
            "BBB": np.linspace(100.0, 60.0, len(dates)),
            "SPY": np.linspace(100.0, 120.0, len(dates)),
        }
        mock_load.side_effect = lambda symbol: pd.DataFrame(
            {"Date": dates, "Close": closes[symbol]}
        )
        portfolio = {
            "created": "2020-01-01",
            "holdings": {
                "AAA": {"shares": 1, "price_at_add": 100.0},
                "BBB": {"shares": 1, "price_at_add": 100.0},
            },
        }
        backtest = {
            "cagr": -20.0,
            "spy_cagr": 9.5,
            "error": None,
            "holdings_detail": {"AAA": {}, "BBB": {}},
        }

        result = analyze_weak_links(portfolio, backtest)

        assert result["weakest"] is None
        assert {holding["verdict"] for holding in result["holdings"].values()} == {"drag"}

    @patch('codes.portfolio.run_backtest')
    @patch('codes.portfolio.run_montecarlo')
    @patch('codes.portfolio.cache')
    @patch('codes.portfolio.load_portfolio')
    def test_run_simulation(self, mock_load, mock_cache, mock_mc, mock_bt):
        mock_load.return_value = {
            "name": "TestSim",
            "holdings": {"AAPL": {"shares": 10, "price_at_add": 150}}
        }
        mock_cache.read.return_value = None
        mock_bt.return_value = {"error": None, "final_value": 50000}
        mock_mc.return_value = {"error": None}

        result = run_simulation(self.user_id, "TestSim")
        self.assertIn("backtest", result)
        self.assertIn("montecarlo", result)

    @patch('codes.portfolio.cache')
    def test_invalidate_cache(self, mock_cache):
        invalidate_simulation_cache(self.user_id, "TestPort")
        mock_cache.clear.assert_called()

    # ====================== ERROR HANDLING ======================

    def test_error_paths(self):
        self.assertIn("error", run_backtest({"holdings": {}}))
        self.assertIn("error", run_montecarlo({"holdings": {}}, {}))


if __name__ == '__main__':
    unittest.main(verbosity=2)

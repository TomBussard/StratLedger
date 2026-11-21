import unittest

import numpy as np
import pandas as pd

from strategies import InvestmentStrategies


class StrategyHistoryTest(unittest.TestCase):
    def test_cutoff_and_direction_of_returns(self):
        strategy = InvestmentStrategies(":memory:")
        connection = strategy.db_manager.conn
        self.addCleanup(connection.close)
        connection.execute("CREATE TABLE SAMPLE_data (Date TEXT, Close REAL)")
        dates = pd.bdate_range("2023-01-02", periods=254).strftime("%Y-%m-%d")
        moves = np.tile([0.012, -0.006], 126)
        prices = 100 * np.exp(np.r_[0, np.cumsum(moves)])
        connection.executemany("INSERT INTO SAMPLE_data VALUES (?, ?)", zip(dates[:253], prices))
        connection.execute("INSERT INTO SAMPLE_data VALUES (?, ?)", (dates[-1], 9999))

        history = strategy.get_market_data(["SAMPLE"], dates[-2])["SAMPLE"]
        self.assertEqual(len(history), 252)
        self.assertEqual(history.iloc[0]["Date"], dates[-2])
        np.testing.assert_allclose(history["Returns"], moves[::-1], atol=1e-12)
        expected = moves.std(ddof=1) * np.sqrt(252)
        self.assertAlmostEqual(history.iloc[0]["Volatility"], expected)
        self.assertAlmostEqual(strategy.calculate_portfolio_volatility(history[["Returns"]]), expected)


if __name__ == "__main__":
    unittest.main()

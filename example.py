"""Use the dashboard's position logic to value a small fictional ledger."""
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from performances import PortfolioAnalyzer


def example():
    with TemporaryDirectory() as location:
        database = Path(location) / "example.db"
        dates = pd.date_range("2024-01-01", periods=6, freq="W-MON")
        with closing(sqlite3.connect(database)) as connection:
            connection.executescript("""
                CREATE TABLE Products (id INTEGER PRIMARY KEY, ticker TEXT, type TEXT);
                CREATE TABLE Deals (portefeuille_id INTEGER, produit_id INTEGER, date TEXT,
                                    type_operation TEXT, quantite REAL);
                CREATE TABLE DEMO_data (Date TEXT, Close REAL, Returns REAL);
                INSERT INTO Products VALUES (1, 'DEMO', 'stock');
                INSERT INTO Deals VALUES (1, 1, '2024-01-01', 'achat', 10);
                INSERT INTO Deals VALUES (1, 1, '2024-01-15', 'achat', 5);
                INSERT INTO Deals VALUES (1, 1, '2024-01-29', 'vente', 4);
            """)
            prices = [100, 104, 101, 98, 105, 102]
            for date, price in zip(dates, prices):
                connection.execute("INSERT INTO DEMO_data VALUES (?, ?, ?)",
                                   (date.strftime("%Y-%m-%d"), price, 0))
            connection.commit()
        analyser = PortfolioAnalyzer(str(database))
        rows = []
        for date in dates.strftime("%Y-%m-%d"):
            positions = analyser.get_portfolio_positions(1, date)
            value, _ = analyser.get_portfolio_value_and_return(1, date)
            rows.append((date, positions["position"].iloc[0], value))
        return pd.DataFrame(rows, columns=["Date", "Shares", "Holdings value"])


if __name__ == "__main__":
    print(example().to_string(index=False))


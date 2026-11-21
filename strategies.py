import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from database_manager import DatabaseManager


class InvestmentStrategies:
    def __init__(self, db_name="fund_management.db"):
        self.db_manager = DatabaseManager(db_name)
        self.db_manager.connect()
        self.volatility_window = 252
        self.max_monthly_trades = 2
        self.target_volatility = 0.10

    def get_products_by_strategy(self, strategy, portfolio_id):
        """Recovers only the assets allocated to the client"""
        with self.db_manager.conn:
            allocations = self.db_manager.conn.execute(
                """
                SELECT a.actif, p.type
                FROM Allocations a
                JOIN Portfolios po ON a.client_id = po.client_id
                JOIN Products p ON a.actif = p.ticker
                WHERE po.id = ?
            """,
                (portfolio_id,),
            ).fetchall()

            if not allocations:
                print(f"Aucune allocation trouvée pour portfolio {portfolio_id}")
                return []

            filtered_tickers = []
            for ticker, asset_type in allocations:
                if strategy == "Low risk":
                    filtered_tickers.append(ticker)
                elif strategy == "Low turnover" and asset_type in ["Stock", "ETF"]:
                    filtered_tickers.append(ticker)
                elif strategy == "High yield equity" and asset_type == "Stock":
                    filtered_tickers.append(ticker)

            print(f"Produits trouvés pour portfolio {portfolio_id}: {filtered_tickers}")
            return filtered_tickers

    def calculate_portfolio_volatility(self, returns_df):
        """Calculates portfolio volatility"""
        if returns_df.empty:
            return 0

        cov_matrix = returns_df.cov() * 252
        n_assets = len(returns_df.columns)
        if n_assets == 0:
            return 0

        weights = np.array([1 / n_assets] * n_assets)
        portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
        return np.sqrt(portfolio_variance)

    def calculate_returns(self, prices):
        """Calculate logarithmic yields"""
        return np.log(prices / prices.shift(1))

    def get_market_data(self, tickers, date):
        """Recovers and prepares market data up to a specific date"""
        conn = self.db_manager.conn
        market_data = {}

        for ticker in tickers:
            try:
                table_name = f"{ticker.replace('-', '_')}_data"
                df = pd.read_sql_query(
                    f"""
                    SELECT * FROM "{table_name}"
                    WHERE Date <= ?
                    ORDER BY Date DESC
                    LIMIT ?
                """,
                    conn,
                    params=(date, self.volatility_window + 1),
                )

                if df.empty:
                    print(f"Aucune donnée trouvée pour {ticker} à la date {date}")
                    continue

                if "Close" not in df.columns and "Adj_Close" in df.columns:
                    df["Close"] = df["Adj_Close"]

                if "Close" not in df.columns:
                    print(f"Pas de colonne Close pour {ticker}")
                    continue

                # Calculate forward in time, then put the latest observations first for the signals.
                df = df.iloc[::-1].copy()
                df["Returns"] = self.calculate_returns(df["Close"])
                df["Volatility"] = df["Returns"].rolling(
                    window=self.volatility_window
                ).std() * np.sqrt(252)

                market_data[ticker] = df.iloc[::-1].head(self.volatility_window).set_index("Date", drop=False)

            except Exception as e:
                print(f"Erreur lors du chargement des données pour {ticker}: {e}")

        return market_data

    def get_current_position(self, portfolio_id, ticker, date):
        """Recovers the current position for an asset on a given date"""
        query = """
            WITH PositionSum AS (
                SELECT
                    SUM(CASE
                        WHEN type_operation = 'achat' THEN quantite
                        WHEN type_operation = 'vente' THEN -quantite
                    END) as position
                FROM Deals d
                JOIN Products p ON d.produit_id = p.id
                WHERE d.portefeuille_id = ?
                AND p.ticker = ?
                AND d.date <= ?
            )
            SELECT COALESCE(position, 0) as position FROM PositionSum
        """
        result = self.db_manager.conn.execute(query, (portfolio_id, ticker, date)).fetchone()
        return result[0] if result else 0

    def apply_low_risk_strategy(self, data, portfolio_id, date):
        """Strategy for annualized volatility of 10%"""
        decisions = []

        # Calculate the volatility of the current portfolio
        portfolio_returns = pd.DataFrame()
        for ticker, df in data.items():
            if "Returns" not in df.columns or df.empty:
                continue
            portfolio_returns[ticker] = df["Returns"]

        portfolio_vol = self.calculate_portfolio_volatility(portfolio_returns)

        for ticker, df in data.items():
            if "Returns" not in df.columns or df.empty:
                continue

            # Use longer periods
            returns_10d = df["Returns"].head(10).mean()
            returns_30d = df["Returns"].head(30).mean()
            volatility = df["Returns"].head(30).std() * np.sqrt(252)
            current_position = self.get_current_position(portfolio_id, ticker, date)

            # Check the type of asset
            asset_type = self.db_manager.conn.execute(
                "SELECT type FROM Products WHERE ticker = ?", (ticker,)
            ).fetchone()[0]

            if current_position > 0:
                if (
                    (returns_30d < -0.02 and asset_type == "Stock")  # -2% over 30 days for shares
                    or (returns_30d < -0.01 and asset_type == "Bond")  # -1% over 30 days for bonds
                    or volatility > self.target_volatility * 1.5  # 50% above target
                ):
                    quantity = min(
                        current_position, max(5, int(current_position * 0.25))
                    )  # Vendre max 25%
                    decisions.append((portfolio_id, ticker, "vente", quantity))
            else:
                if (
                    returns_10d > 0
                    and returns_30d > 0
                    and volatility < self.target_volatility * 1.2
                ):
                    # Volatility-Based Position Size
                    position_size = int(
                        10000 / (volatility * 100)
                    )  # The lower the volatility, the greater the position
                    position_size = max(5, min(20, position_size))  # Born between 5 and 20
                    decisions.append((portfolio_id, ticker, "achat", position_size))

        return decisions

    def apply_low_turnover_strategy(self, data, portfolio_id, date):
        """Strategy limited to 2 trades per month (1 trade every 2 Mondays)"""
        decisions = []

        # Convert date to datetime for manipulation
        current_date = pd.to_datetime(date)
        start_of_month = current_date.replace(day=1)

        # Determines whether it is an "active" Monday (1st or 3rd Monday of the month)
        week_number = (current_date.day - 1) // 7 + 1
        is_trading_week = week_number in [1, 3]  # Only 1st and 3rd Monday

        if not is_trading_week:
            return decisions

        # Check if we've ever made a trade this week.
        trades_this_week = self.db_manager.conn.execute(
            """
            SELECT COUNT(*) FROM Deals
            WHERE portefeuille_id = ?
            AND date = ?
        """,
            (portfolio_id, date),
        ).fetchone()[0]

        if trades_this_week > 0:
            return decisions

        # Continue with trading logic only if it is an "active" Monday
        for ticker, df in data.items():
            if "Returns" not in df.columns or df.empty:
                continue

            returns_5d = df["Returns"].head(5).mean()
            returns_20d = df["Returns"].head(20).mean()
            current_position = self.get_current_position(portfolio_id, ticker, date)

            if current_position > 0:
                if returns_5d < returns_20d * 0.90:
                    quantity = min(current_position, random.randint(15, 25))
                    decisions.append((portfolio_id, ticker, "vente", quantity))
                    break  # Only one trade per active Monday
            else:
                if returns_5d > returns_20d * 1.10:
                    decisions.append((portfolio_id, ticker, "achat", random.randint(15, 25)))
                    break  # Only one trade per active Monday

        return decisions

    def apply_high_yield_strategy(self, data, portfolio_id, date):
        """Aggressive action strategy with risk management"""
        decisions = []
        max_position_size = 25  # Taille maximale de position

        for ticker, df in data.items():
            if "Returns" not in df.columns or df.empty:
                continue

            returns_5d = df["Returns"].head(5).mean()
            returns_10d = df["Returns"].head(10).mean()
            returns_30d = df["Returns"].head(30).mean()
            volatility = df["Returns"].head(30).std() * np.sqrt(252)
            current_position = self.get_current_position(portfolio_id, ticker, date)

            if current_position > 0:
                # Stop loss to -7% or downward trend
                if (
                    returns_30d < -0.07  # Stop loss
                    or (
                        returns_5d < 0 and returns_10d < 0 and returns_30d < 0
                    )  # Confirmed downtrend
                ):
                    quantity = min(current_position, max(5, int(current_position * 0.75)))
                    decisions.append((portfolio_id, ticker, "vente", quantity))
            else:
                # Purchase on positive momentum
                if (
                    returns_5d > 0
                    and returns_10d > 0
                    and returns_30d > 0  # Growth trend confirmed
                    and volatility < 0.40  # Maximum volatility of 40%
                ):
                    # Position size inversely proportional to volatility
                    position_size = int(15000 / (volatility * 100))
                    position_size = max(5, min(max_position_size, position_size))
                    decisions.append((portfolio_id, ticker, "achat", position_size))

        return decisions

    def get_monthly_trades_count(self, portfolio_id, month):
        """Counts the number of trades for a portfolio in a given month"""
        query = """
            SELECT COUNT(*) FROM Deals
            WHERE portefeuille_id = ?
            AND strftime('%Y-%m', date) = ?
        """
        count = self.db_manager.conn.execute(query, (portfolio_id, month)).fetchone()[0]
        return count

    def apply_strategy(self, strategy, portfolio_id, date):
        """Apply the appropriate strategy according to profile"""
        tickers = self.get_products_by_strategy(strategy, portfolio_id)
        if not tickers:
            print(f"Aucun actif trouvé pour {strategy}")
            return []

        market_data = self.get_market_data(tickers, date)
        if not market_data:
            print(f"Aucune donnée de marché pour {strategy} à la date {date}")
            return []

        if strategy == "Low risk":
            return self.apply_low_risk_strategy(market_data, portfolio_id, date)
        elif strategy == "Low turnover":
            return self.apply_low_turnover_strategy(market_data, portfolio_id, date)
        elif strategy == "High yield equity":
            return self.apply_high_yield_strategy(market_data, portfolio_id, date)

        return []

    def execute_strategies(self, date=None):
        """Runs strategies for all portfolios"""
        if date is None:
            date = datetime.today()
            while date.weekday() != 0:
                date = date - timedelta(days=1)
            date = date.strftime("%Y-%m-%d")

        print(f"Exécution des stratégies pour {date}")

        query = """
            SELECT p.id, c.profil_risque
            FROM Portfolios p
            JOIN Clients c ON p.client_id = c.id
        """

        with self.db_manager.conn:
            portfolios = self.db_manager.conn.execute(query).fetchall()

        if not portfolios:
            print("Aucun portefeuille trouvé.")
            return

        print(f"Portefeuilles trouvés : {portfolios}")

        all_decisions = []
        for portfolio_id, profil_risque in portfolios:
            decisions = self.apply_strategy(profil_risque, portfolio_id, date)
            if decisions:
                all_decisions.extend(decisions)

        print(f"Décisions générées pour {date}: {all_decisions}")
        self.store_deals(all_decisions, date)

    def store_deals(self, deals, date):
        """Record transactions in the database"""
        if not deals:
            print(f"Aucune transaction pour {date}")
            return

        with self.db_manager.conn:
            for portfolio_id, ticker, type_operation, quantite in deals:
                try:
                    produit_id = self.db_manager.conn.execute(
                        "SELECT id FROM Products WHERE ticker = ?", (ticker,)
                    ).fetchone()

                    if not produit_id:
                        print(f" Produit {ticker} introuvable")
                        continue

                    existing = self.db_manager.conn.execute(
                        """
                        SELECT COUNT(*) FROM Deals
                        WHERE portefeuille_id = ?
                        AND produit_id = ?
                        AND date = ?
                        AND type_operation = ?
                    """,
                        (portfolio_id, produit_id[0], date, type_operation),
                    ).fetchone()[0]

                    if not existing:
                        df = pd.read_sql_query(
                            f"""
                            SELECT return, volatilite
                            FROM Returns
                            WHERE product_id = ?
                            AND date <= ?
                            ORDER BY date DESC
                            LIMIT 20
                        """,
                            self.db_manager.conn,
                            params=(produit_id[0], date),
                        )

                        volatilite_periode = df["volatilite"].mean() if not df.empty else None
                        rendement_periode = df["return"].mean() if not df.empty else None

                        self.db_manager.conn.execute(
                            """
                            INSERT INTO Deals (
                                portefeuille_id, produit_id, type_operation,
                                quantite, date, volatilite_periode, rendement_periode
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                portfolio_id,
                                produit_id[0],
                                type_operation,
                                quantite,
                                date,
                                volatilite_periode,
                                rendement_periode,
                            ),
                        )

                        print(
                            f"Transaction ajoutée : {portfolio_id} | {ticker} | {type_operation} {quantite}"
                        )

                except Exception as e:
                    print(f"Erreur lors de l'insertion : {e}")

            self.db_manager.conn.commit()


if __name__ == "__main__":
    strategies = InvestmentStrategies()
    today = datetime.today()
    for i in range(4):
        date = today - timedelta(days=i * 7)
        while date.weekday() != 0:
            date = date - timedelta(days=1)
        strategies.execute_strategies(date.strftime("%Y-%m-%d"))

import sqlite3
from datetime import datetime, timedelta
from strategies import InvestmentStrategies

DB_NAME = "fund_management.db"


class BaseUpdater:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME)
        self.cursor = self.conn.cursor()
        self.strategies = InvestmentStrategies(DB_NAME)

    def store_deals(self):
        """Implements strategies and stores transactions"""
        print("Génération des transactions...")

        # Recover all existing portfolios once
        portfolios = self.cursor.execute("""
            SELECT DISTINCT p.id, c.profil_risque
            FROM Portfolios p
            JOIN Clients c ON p.client_id = c.id
        """).fetchall()

        # For each Monday of the last 4 weeks
        today = datetime.today()
        for i in range(4):
            date = today - timedelta(days=i * 7)
            while date.weekday() != 0:
                date = date - timedelta(days=1)

            print(f"Exécution des stratégies pour {date.strftime('%Y-%m-%d')}")

            # For each existing portfolio
            for portfolio_id, strategy in portfolios:
                print(f"Application de la stratégie {strategy} pour portfolio {portfolio_id}")

                # Generates and stores decisions
                decisions = self.strategies.apply_strategy(
                    strategy, portfolio_id, date.strftime("%Y-%m-%d")
                )

                if decisions:
                    self.strategies.store_deals(decisions, date.strftime("%Y-%m-%d"))
                    print(f"{len(decisions)} transactions générées pour portfolio {portfolio_id}")

        print("Génération des transactions terminée")

    def update_portfolios(self):
        """Updates portfolio positions"""
        print("Mise à jour des positions des portefeuilles...")

        # Recovers all transactions
        self.cursor.execute("""
            SELECT
                d.portefeuille_id, d.produit_id, d.type_operation,
                d.quantite, pr.ticker
            FROM Deals d
            JOIN Products pr ON d.produit_id = pr.id
            ORDER BY d.date
        """)
        deals = self.cursor.fetchall()

        if not deals:
            print("Aucune transaction trouvée")
            return

        print(f"Traitement de {len(deals)} transactions...")

        # Keep track of current positions
        current_positions = {}
        for deal in deals:
            portefeuille_id, produit_id, type_operation, quantite, ticker = deal

            if portefeuille_id not in current_positions:
                current_positions[portefeuille_id] = {}

            if ticker not in current_positions[portefeuille_id]:
                current_positions[portefeuille_id][ticker] = {
                    "quantity": 0,
                    "produit_id": produit_id,
                }

            # Update position
            if type_operation == "achat":
                current_positions[portefeuille_id][ticker]["quantity"] += quantite
            else:  # vente
                current_positions[portefeuille_id][ticker]["quantity"] -= quantite

        # Update database
        for portefeuille_id, positions in current_positions.items():
            # Delete all current positions
            self.cursor.execute(
                """
                DELETE FROM Portfolios_Holdings
                WHERE portefeuille_id = ?
            """,
                (portefeuille_id,),
            )

            # Insert new positions
            for ticker, details in positions.items():
                if details["quantity"] > 0:
                    self.cursor.execute(
                        """
                        INSERT INTO Portfolios_Holdings (
                            portefeuille_id, produit_id, quantite
                        ) VALUES (?, ?, ?)
                    """,
                        (portefeuille_id, details["produit_id"], details["quantity"]),
                    )
                    print(
                        f" Position mise à jour: Portfolio {portefeuille_id} | {ticker} | {details['quantity']}"
                    )

        self.conn.commit()
        print("\n Positions des portefeuilles mises à jour")

    def close(self):
        """Close the connection to the database"""
        if hasattr(self, "strategies"):
            self.strategies.db_manager.close()
        if hasattr(self, "conn"):
            self.conn.close()
            self.conn = None
            self.cursor = None


if __name__ == "__main__":
    updater = BaseUpdater()
    updater.store_deals()
    updater.update_portfolios()
    updater.close()
    print("Mise à jour terminée avec succès")

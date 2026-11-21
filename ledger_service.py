"""SQLite connections and transaction generation shared by the dashboard and CLI."""

from datetime import datetime, timedelta

from base_update import BaseUpdater
from data_collector import DataCollector
from database_manager import DatabaseManager, portfolio_connection
from strategies import InvestmentStrategies

DB_NAME = "fund_management.db"


def get_connection():
    return portfolio_connection(DB_NAME)


def prepare_database(reset=False):
    manager = DatabaseManager(DB_NAME)
    manager.connect()
    try:
        if reset and not manager.reset_database():
            return False
        manager.create_tables()
        manager.populate_initial_data()
        return True
    finally:
        manager.close()


def generate_transactions_for_client(client_id, start_date=None, end_date=None):
    """Generates transactions for a customer over a given period"""
    if start_date is None:
        start_date = datetime.today() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.today()

    # Initiate strategies
    strategies = InvestmentStrategies()

    # Recovers the client portfolio
    with get_connection() as conn:
        portfolio = conn.execute(
            """
            SELECT p.id, c.profil_risque
            FROM Portfolios p
            JOIN Clients c ON p.client_id = c.id
            WHERE c.id = ?
        """,
            (client_id,),
        ).fetchone()

        if not portfolio:
            return

        portfolio_id, strategy = portfolio

        # Removes old transactions over the period
        conn.execute(
            """
            DELETE FROM Deals
            WHERE portefeuille_id = ?
            AND date BETWEEN ? AND ?
        """,
            (portfolio_id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
        )
        conn.commit()

    # Recovers market data for the entire period only once
    collector = DataCollector(
        start_date=start_date.strftime("%Y-%m-%d"), end_date=end_date.strftime("%Y-%m-%d")
    )
    collector.fetch_data()

    # For each Monday in the period
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() == 0:  # If it's a Monday
            # Generates and stores decisions
            decisions = strategies.apply_strategy(
                strategy, portfolio_id, current_date.strftime("%Y-%m-%d")
            )

            if decisions:
                strategies.store_deals(decisions, current_date.strftime("%Y-%m-%d"))
                print(f"Transactions générées pour {current_date.strftime('%Y-%m-%d')}")

        current_date += timedelta(days=1)

    # Updates portfolio positions
    updater = BaseUpdater()
    updater.update_portfolios()
    updater.close()

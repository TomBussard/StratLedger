"""Explore a six-week example or open the full portfolio simulator."""

import os
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

from base_update import BaseUpdater
from data_collector import DataCollector
from example import example
from ledger_service import (
    DB_NAME,
    generate_transactions_for_client,
    get_connection,
    prepare_database,
)
from performances import PortfolioAnalyzer

st.set_page_config(page_title="StratLedger", layout="wide")
st.title("StratLedger")
workspace = st.sidebar.radio("Workspace", ["Ledger walk-through", "Portfolio simulator"])
if workspace == "Ledger walk-through":
    st.write("Follow three trades through six weekly valuations of a fictional account.")
    ledger = example().set_index("Date")
    left, right = st.columns(2)
    left.metric("Closing position", f"{ledger['Shares'].iloc[-1]:g} shares")
    right.metric("Final holdings value", f"{ledger['Holdings value'].iloc[-1]:,.0f}")
    st.line_chart(ledger["Shares"])
    st.dataframe(ledger, use_container_width=True)
    st.caption(
        "Holdings value excludes cash. Open the simulator to explore the strategy and benchmark views."
    )
    st.stop()

if not os.path.exists(DB_NAME):
    prepare_database()
st.write(
    "Choose a sample client and a risk profile to inspect trades, holdings and weekly returns."
)
st.sidebar.header("Clients")

# Recovers existing customers
with get_connection() as conn:
    clients = conn.execute("SELECT * FROM Clients").fetchall()

client_options = {client["nom"]: client["id"] for client in clients}

# Selection of an existing client
selected_client = None
if client_options:
    selected_client = st.sidebar.selectbox("Choose a client", list(client_options.keys()))

    with get_connection() as conn:
        client_profile = conn.execute(
            "SELECT profil_risque FROM Clients WHERE id = ?", (client_options[selected_client],)
        ).fetchone()["profil_risque"]

        st.sidebar.info(f"Profil de risque : {client_profile}")

# Add a new customer
new_client_name = st.sidebar.text_input("New client name")
risk_options = ["Low risk", "Low turnover", "High yield equity"]
new_client_risk = st.sidebar.selectbox("Risk profile", risk_options)

if st.sidebar.button("Add client"):
    if new_client_name:
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO Clients (nom, profil_risque) VALUES (?, ?)",
                (new_client_name, new_client_risk),
            )
            client_id = cursor.lastrowid

            volatilite_cible = 0.10 if new_client_risk == "Low risk" else None
            max_trades = 2 if new_client_risk == "Low turnover" else None

            cursor.execute(
                """INSERT INTO Portfolios (client_id, nom, volatilite_cible, max_trades_mensuel)
                   VALUES (?, ?, ?, ?)""",
                (client_id, f"Portefeuille de {new_client_name}", volatilite_cible, max_trades),
            )

            if new_client_risk == "Low risk":
                assets = ["TLT", "LQD", "TIP", "AGG", "SPY", "BND"]
            elif new_client_risk == "Low turnover":
                assets = ["AAPL", "MSFT", "JNJ", "V", "KO", "PG", "SPY", "VT"]
            else:  # High yield equity
                assets = ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA", "META", "AMZN", "NFLX"]

            for asset in assets:
                cursor.execute(
                    "INSERT INTO Allocations (client_id, actif) VALUES (?, ?)", (client_id, asset)
                )

            conn.commit()
            st.success(f"Added client {new_client_name}.")
            st.rerun()

# Control buttons in the sidebar
if st.sidebar.button("Regenerate transactions"):
    if selected_client:
        updater = BaseUpdater()
        updater.store_deals()
        updater.update_portfolios()
        updater.close()
        st.sidebar.success("Successfully regenerated transactions!")
        st.rerun()

if st.sidebar.button("Reset the sample database"):
    if prepare_database(reset=True):
        st.sidebar.success("Database successfully reset!")
    else:
        st.sidebar.error("Error resetting database.")
    st.rerun()

# Benchmark selector for beta calculation
st.sidebar.subheader("Benchmark")
benchmark_ticker = st.sidebar.selectbox(
    "Choose a benchmark to calculate the beta:", ["SPY", "QQQ", "VT", "URTH", "XLK", "XLF", "IWM"]
)

# Viewing main content
if selected_client:
    st.header(f"Portfolio for {selected_client}")

    # Selection of period
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start date",
            value=datetime(2015, 1, 1),
            min_value=datetime(2010, 1, 1),
            max_value=datetime.today(),
        )
    with col2:
        end_date = st.date_input(
            "End date",
            value=datetime.today(),
            min_value=datetime(2010, 1, 1),
            max_value=datetime.today(),
        )

    # Get the ID from the portfolio
    with get_connection() as conn:
        portfolio_id = conn.execute(
            "SELECT id FROM Portfolios WHERE client_id = ?", (client_options[selected_client],)
        ).fetchone()["id"]

    # Asset management
    st.header("Holdings")

    # Recovering current client assets
    with get_connection() as conn:
        assets_data = conn.execute(
            """
            SELECT a.actif, p.type
            FROM Allocations a
            JOIN Products p ON a.actif = p.ticker
            WHERE a.client_id = ?
        """,
            (client_options[selected_client],),
        ).fetchall()

    # Arranges assets by class
    asset_classes = {"Stock": [], "Bond": [], "ETF": []}

    for asset in assets_data:
        asset_classes[asset[1]].append(asset[0])

    # Asset selection interface
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Equities")
        available_stocks = [
            "AAPL",
            "GOOGL",
            "MSFT",
            "TSLA",
            "NVDA",
            "META",
            "AMZN",
            "JNJ",
            "V",
            "KO",
            "PG",
            "PFE",
            "BRK-B",
            "WMT",
            "MCD",
            "JPM",
            "CVX",
            "PEP",
            "INTC",
            "NFLX",
        ]

        selected_stocks = st.multiselect(
            "Select Actions", available_stocks, default=asset_classes["Stock"]
        )

    with col2:
        st.subheader("Bonds")
        available_bonds = ["TLT", "LQD", "TIP", "AGG", "HYG", "MUB", "SHY", "IEF", "TBT", "BND"]
        selected_bonds = st.multiselect(
            "Select Bonds", available_bonds, default=asset_classes["Bond"]
        )

    with col3:
        st.subheader(" ETFs")
        available_etfs = ["SPY", "QQQ", "IWM", "URTH", "XLK", "XLV", "XLF", "XLY", "XLE", "VT"]
        selected_etfs = st.multiselect("Select ETFs", available_etfs, default=asset_classes["ETF"])

    # Save changes
    if st.button("Save changes"):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM Allocations WHERE client_id = ?", (client_options[selected_client],)
            )

            all_selected = selected_stocks + selected_bonds + selected_etfs
            for asset in all_selected:
                cursor.execute(
                    "INSERT INTO Allocations (client_id, actif) VALUES (?, ?)",
                    (client_options[selected_client], asset),
                )

            conn.commit()

            # Regenerates transactions for the selected period
            generate_transactions_for_client(client_options[selected_client], start_date, end_date)

            st.success("Successfully Saved Changes!")
            st.rerun()

    # Market Data Display
    selected_assets = selected_stocks + selected_bonds + selected_etfs
    if selected_assets:
        st.header("Market data")

        collector = DataCollector(
            tickers=selected_assets,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )
        collector.fetch_data()
        data = collector.get_data()

        if data:
            # Creating Combined DataFrame
            combined_df = pd.DataFrame()
            for ticker, df in data.items():
                if df.index.name == "Date" or "Date" not in df.columns:
                    df = df.reset_index()

                if "Close" not in df.columns:
                    continue

                close_df = df[["Date", "Close"]].copy()
                close_df = close_df.rename(columns={"Close": ticker})

                if combined_df.empty:
                    combined_df = close_df
                else:
                    combined_df = pd.merge(combined_df, close_df, on="Date", how="outer")

            if not combined_df.empty:
                combined_df = combined_df.sort_values("Date").set_index("Date").ffill().bfill()

                st.subheader("Closing price")
                st.dataframe(combined_df)

                # Standardised performance
                def normalize_base100(df):
                    return df.div(df.iloc[0]).mul(100)

                st.subheader("Standardized performance (Base 100)")
                normalized_df = normalize_base100(combined_df)
                st.dataframe(normalized_df)
                st.line_chart(normalized_df)

    # Description of the chosen strategy
    st.subheader("Investment strategy implemented")

    if client_profile == "Low risk":
        st.markdown(
            "This strategy aims to achieve a 10% annualised volatility** target.\nIt favours bonds and defensive ETFs.\nPurchasing signals are triggered when recent returns are positive and moderate volatility.\nSales can be made if an asset becomes too volatile or shows a downward trend."
        )
    elif client_profile == "Low turnover":
        st.markdown(
            "This strategy aims at **limiting transactions to 2 transactions per month**.\nIt promotes stable positions, in actions and ETF, with a slow rotation logic.\nSignals are triggered only on the **1st and 3rd Monday of the month**, according to the evolution of yields over 5 and 20 days."
        )
    elif client_profile == "High yield equity":
        st.markdown(
            "This strategy is oriented towards **high yield research via high volatility stocks**.\nIt is based on short-, medium- and long-term momentum analysis.\nPurchases are triggered if trends are bullish and volatility is controlled.\nA stop-loss is activated if the trend is reversed or if losses exceed -7% over 30 days."
        )

    # Transaction history
    st.header("Transaction history")
    with get_connection() as conn:
        transactions = pd.read_sql_query(
            """
            SELECT
                d.date as "Date",
                pr.ticker as "Actif",
                pr.type as "Type d'actif",
                d.type_operation as "Opération",
                d.quantite as "Quantité"
            FROM Deals d
            JOIN Products pr ON d.produit_id = pr.id
            JOIN Portfolios p ON d.portefeuille_id = p.id
            WHERE p.client_id = ?
            AND d.date BETWEEN ? AND ?
            ORDER BY d.date DESC
        """,
            conn,
            params=(
                client_options[selected_client],
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            ),
        )

        if not transactions.empty:
            st.dataframe(transactions)
        else:
            st.info("No transactions over the selected period.")

    # Current portfolio composition
    st.subheader("Portfolio composition")
    analyzer = PortfolioAnalyzer()
    composition = analyzer.get_portfolio_composition(portfolio_id)
    if not composition.empty:
        composition["poids"] = composition["poids"].map("{:.2f}%".format)
        composition["valeur_marche"] = composition["valeur_marche"].map("${:,.2f}".format)
        composition["prix"] = composition["prix"].map("${:.2f}".format)
        st.dataframe(composition)

    # Portfolio performance
    st.header("Portfolio Performance")

    # Calculates and displays performance metrics
    metrics = analyzer.calculate_performance_metrics(
        portfolio_id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
    )
    # Graph of weekly yields
    st.subheader("Portfolio returns")
    weekly_returns = metrics["weekly_returns"]
    if not weekly_returns.empty:
        st.line_chart(weekly_returns.set_index("date")["return"])

    # Show main metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(
            "Rendement Total",
            f"{metrics['rendement_total']:.2%}",
            delta=f"{metrics['rendement_annualise']:.2%} (annualised)",
        )
    with col2:
        st.metric("Volatility Annualized", f"{metrics['volatilite_annualisee']:.2%}")
    with col3:
        st.metric("Ratio de Sharpe", f"{metrics['ratio_sharpe']:.2f}")
    with col4:
        st.metric("Drawdown Maximum", f"{metrics['drawdown_max']:.2%}")
    with col5:

        def get_weekly_returns(ticker, dates):
            start = min(dates)
            end = max(dates)
            with get_connection() as conn:
                table = f"{ticker}_data"
                df = pd.read_sql_query(
                    f"""
                    SELECT Date, Returns FROM {table}
                    WHERE Date BETWEEN ? AND ?
                    ORDER BY Date
                """,
                    conn,
                    params=(start, end),
                )
                df = df.dropna()
                df["Date"] = pd.to_datetime(df["Date"])
                return df.set_index("Date")["Returns"]

        if not weekly_returns.empty:
            benchmark_returns = get_weekly_returns(benchmark_ticker, list(weekly_returns["date"]))
            portfolio_returns = weekly_returns.set_index("date")["return"]

            portfolio_returns.index = pd.to_datetime(portfolio_returns.index).date
            benchmark_returns.index = pd.to_datetime(benchmark_returns.index).date

            common_index = benchmark_returns.index.intersection(portfolio_returns.index)

            if len(common_index) > 0:
                x = benchmark_returns.loc[common_index]
                y = portfolio_returns.loc[common_index]
                beta = np.cov(y, x)[0, 1] / np.var(x)
                alpha = (y.mean() - beta * x.mean()) * 52  # Annualisation
                st.metric(f"Bêta ({benchmark_ticker})", f"{beta:.2f}")
                st.metric(f"Alpha annuel ({benchmark_ticker})", f"{alpha:.2%}")
            else:
                st.metric(f"Bêta ({benchmark_ticker})", "N/A")
                st.metric(f"Alpha annuel ({benchmark_ticker})", "N/A")

    # Graph of cumulative yield changes
    st.subheader("Changes in cumulative portfolio returns (Base 100)")
    if not weekly_returns.empty:
        evolution_df = weekly_returns.copy()
        evolution_df["rendement_cumule"] = (1 + evolution_df["return"]).cumprod() * 100
        st.line_chart(evolution_df.set_index("date")["rendement_cumule"])

    # Drawdown curve
    st.subheader("Drawdown in time")
    if not weekly_returns.empty:
        cumulative = (1 + weekly_returns["return"]).cumprod()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak
        drawdown_df = pd.DataFrame(
            {"date": weekly_returns["date"], "drawdown": drawdown}
        ).set_index("date")
        st.line_chart(drawdown_df)

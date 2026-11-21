# StratLedger

StratLedger follows a simulated investment portfolio from a strategy decision to the return on the book. A Streamlit dashboard connects market data, transactions and portfolio-level risk metrics through a local SQLite database.

## What you can do

Create a sample client, choose a risk profile and compare the low-risk, low-turnover and high-yield strategy rules. Inspect the resulting trades, positions and weekly performance. The dashboard reports volatility, Sharpe ratio and maximum drawdown.

The [strategy rules](strategies.py) determine which trades to book. The [portfolio analyser](performances.py) reconstructs positions and calculates returns. Historical prices are requested through Yahoo Finance, so data availability can affect a run.

## Reconstruct a position

I used a six-week example to check how the ledger handles successive trades in the same stock. The account bought ten shares, added five and sold four. It finished with **11 shares** worth **1,122** at the final simulated price of 102. The chart shows shares held, so changes in the quote cannot be mistaken for a trade. [Reproducible example](example.py)

![Shares held across six weekly valuations after two buys and one sale](figures/ledger-example.png)

## Run locally

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Launch from the repository root so the app can create its SQLite database in the working directory. Use a sample client to explore the simulator.

Run `python example.py` for the offline ledger walk-through. Its temporary database contains only the fictional trades above.

Portfolio by **Tom Bussard**.

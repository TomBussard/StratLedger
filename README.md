# StratLedger

StratLedger follows a simulated investment portfolio from a strategy decision to the return on the book. A Streamlit dashboard connects market data, transactions and portfolio-level risk metrics through a local SQLite database.

## What you can do

Create a sample client, choose a risk profile and compare the low-risk, low-turnover and high-yield strategy rules. Inspect the resulting trades, positions and weekly performance. The dashboard reports volatility, Sharpe ratio and maximum drawdown.

The [strategy rules](strategies.py) determine which trades to book. The [portfolio analyser](performances.py) reconstructs positions and calculates returns. Historical prices are requested through Yahoo Finance, so data availability can affect a run.

## Reconstruct a position

I used a six-week example to check how the ledger handles successive trades in the same stock. The account bought ten shares, added five and sold four. It finished with **11 shares** worth **1,122** at the final simulated price of 102. The chart shows shares held, so changes in the quote cannot be mistaken for a trade. [Reproducible example](example.py)

![Shares held across six weekly valuations after two buys and one sale](figures/ledger-example.png)

## From a trade to a weekly valuation

| Week | Ledger event | Shares held | Closing price | Holdings value |
| --- | --- | ---: | ---: | ---: |
| 1 | Buy 10 | 10 | 100 | 1,000 |
| 3 | Buy 5 | 15 | 101 | 1,515 |
| 5 | Sell 4 | 11 | 105 | 1,155 |
| 6 | No trade | 11 | 102 | 1,122 |

An older sale must keep reducing the position on every later valuation date. The analyser therefore sums signed quantities by product through the cutoff, then attaches the latest available price. The drop from 1,155 to 1,122 in the last row is entirely a price move. These are holdings values. Measuring an investor's gain would also require the cash paid and received.

The dashboard opens with this example and creates its ledger in a temporary directory. Choose **Portfolio simulator** for the sample-client database. Its low-risk, low-turnover and high-yield equity rules feed the same holdings workflow. [Database schema](database_manager.py) · [Connections and transaction generation](ledger_service.py) · [Weekly valuation and performance](performances.py)

## Run locally

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Launch from the repository root so the app can create its SQLite database in the working directory. Use a sample client to explore the simulator.

Run `python example.py` for the offline ledger walk-through. Its temporary database contains only the fictional trades above.

Tom Bussard

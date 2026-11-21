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

I store deals as dated quantities in SQLite. For asset $i$, let $q_{i,k}$ be the signed quantity on trade $k$, positive for a buy and negative for a sale. At each Monday cutoff $t$ I reconstruct the position $Q_{i,t}$ and look up the most recent close $P_{i,t}$ available on or before that date. The holdings value $H_t$ sums the positions I can price.

```math
Q_{i,t}=\sum_{k:\,t_k\le t}q_{i,k},\qquad H_t=\sum_i Q_{i,t}P_{i,t}
```

### How much of a weekly move came from trading?

For one stock the change in holdings value splits exactly into the price move on the opening shares and the change in shares valued at the new close.

```math
H_t-H_{t-1}=Q_{t-1}(P_t-P_{t-1})+(Q_t-Q_{t-1})P_t
```

In week 2 the account held ten shares at 104. In week 3 the price fell to 101, costing **30** on the opening position. The five new shares added **505** at that week's close. Holdings therefore rose by **475**, from **1,040 to 1,515**, even though the stock fell. In the final week the account held 11 shares throughout, so the drop from 105 to 102 explains the entire **33** decline.

The simulator calculates weekly percentage changes in holdings value and clips them to the range from −10% to +10% before computing its risk metrics. In the purchase week, a raw increase of 45.67% therefore enters those metrics as 10%. The ledger example displays the actual holdings values. An investor return across buys and sells would also need cash movements and trade proceeds. [Position reconstruction and weekly metrics](performances.py) · [Six-week ledger](example.py)

The dashboard opens with this example and creates its ledger in a temporary directory. Choose **Portfolio simulator** for the sample-client database. Its low-risk, low-turnover and high-yield equity rules feed the same holdings workflow. [Database schema](database_manager.py) · [Connections and transaction generation](ledger_service.py) · [Weekly valuation and performance](performances.py)

## Run locally

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Launch from the repository root so the app can create its SQLite database in the working directory. Use a sample client to explore the simulator.

Run `python example.py` for the offline ledger walk-through. Its temporary database contains only the fictional trades above.

Tom Bussard

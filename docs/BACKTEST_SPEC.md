# AUREXIS Backtest Specification

Backtesting must attempt to model execution reality rather than only OHLC candle outcomes.

Consider:
- tick data
- bid/ask
- spread
- slippage
- latency
- commission
- swap
- session effects
- news windows
- broker symbol specifications

Validation should include:
- in-sample
- out-of-sample
- walk-forward
- parameter sensitivity
- Monte Carlo/stress analysis

No backtest result is proof of future profitability.

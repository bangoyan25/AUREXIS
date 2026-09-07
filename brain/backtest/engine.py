"""

AUREXIS Backtest Engine — TASK-505 / Phase E.



Runs historical simulation using the EXACT same Brain and Risk code paths as live:

  Tick stream

    → BarBuilder (Closed bars only)

    → SignalPipeline (Brain analytical stages)

    → CandidateSignal

    → RiskEngine (Identical risk limits & position sizing)

    → Simulated Execution (Fill at market bid/ask + slippage)

    → Equity & PnL Ledger Tracking



Mandatory invariant: "Backtest results are not proof of future profitability."

"""



from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from backend.risk.config import RiskConfig
from backend.risk.engine import AccountRiskSnapshot, MarketCondition, RiskEngine
from brain.bar_builder import BarBuilder
from brain.config import BrainConfig
from brain.pipeline import SignalPipeline
from brain.strategy.interfaces import SignalDirection

if TYPE_CHECKING:

    from collections.abc import Sequence
    from datetime import datetime

    from brain.market_data.types import Bar, Tick





@dataclass(frozen=True)

class BacktestConfig:

    """Backtest execution parameters and models."""

    initial_balance_usd: Decimal = Decimal("10000.00")

    symbol: str = "XAUUSD"

    point_value: Decimal = Decimal("0.01")

    contract_size: Decimal = Decimal("100")

    slippage_points: int = 0

    commission_per_lot_usd: Decimal = Decimal("0.00")

    brain_config: BrainConfig = field(default_factory=BrainConfig)

    risk_config: RiskConfig = field(default_factory=RiskConfig)

    timeframe: str = "M1"





@dataclass

class BacktestTrade:

    """Record of an executed backtest trade."""

    trade_id: str

    symbol: str

    side: str  # "BUY" or "SELL"

    entry_time: datetime

    entry_price: Decimal

    volume_lots: Decimal

    stop_loss: Decimal | None

    take_profit: Decimal | None

    exit_time: datetime | None = None

    exit_price: Decimal | None = None

    realized_pnl_usd: Decimal = Decimal("0.00")

    commission_usd: Decimal = Decimal("0.00")

    exit_reason: str | None = None





@dataclass(frozen=True)

class BacktestResult:

    """Summary metrics of backtest run. Backtest results are not proof of future profitability."""

    initial_balance_usd: Decimal

    final_balance_usd: Decimal

    total_net_pnl_usd: Decimal

    total_trades: int

    winning_trades: int

    losing_trades: int

    win_rate_pct: Decimal

    profit_factor: Decimal | None

    max_drawdown_usd: Decimal

    max_drawdown_pct: Decimal

    trades: list[BacktestTrade]

    gross_profit_usd: Decimal = Decimal("0.00")

    gross_loss_usd: Decimal = Decimal("0.00")

    expectancy_usd: Decimal = Decimal("0.00")

    largest_win_usd: Decimal = Decimal("0.00")

    largest_loss_usd: Decimal = Decimal("0.00")

    consecutive_wins: int = 0

    consecutive_losses: int = 0

    disclaimer: str = "Backtest results are not proof of future profitability."






class BacktestEngine:

    """

    Deterministic historical backtest engine.

    Guarantees no lookahead bias by streaming ticks in chronological order.

    """



    def __init__(self, config: BacktestConfig) -> None:

        self._config = config

        self._brain_pipeline = SignalPipeline(config=config.brain_config)

        self._risk_engine = RiskEngine(config=config.risk_config)

        self._bar_builder = BarBuilder(symbol=config.symbol, timeframe=config.timeframe)



    def run(self, ticks: Sequence[Tick]) -> BacktestResult:

        if not ticks:

            return BacktestResult(

                initial_balance_usd=self._config.initial_balance_usd,

                final_balance_usd=self._config.initial_balance_usd,

                total_net_pnl_usd=Decimal("0.00"),

                total_trades=0,

                winning_trades=0,

                losing_trades=0,

                win_rate_pct=Decimal("0.00"),

                profit_factor=None,

                max_drawdown_usd=Decimal("0.00"),

                max_drawdown_pct=Decimal("0.00"),

                trades=[],

            )



        balance = self._config.initial_balance_usd

        peak_equity = balance

        max_drawdown_usd = Decimal("0.00")

        max_drawdown_pct = Decimal("0.00")



        open_positions: list[BacktestTrade] = []

        completed_trades: list[BacktestTrade] = []

        closed_bars: list[Bar] = []



        for tick in ticks:

            # 1. Update and check existing open positions for SL/TP hits

            still_open: list[BacktestTrade] = []

            for pos in open_positions:

                closed = False

                exit_price = None

                exit_reason = None



                if pos.side == "BUY":

                    if pos.stop_loss is not None and tick.bid <= pos.stop_loss:

                        exit_price = pos.stop_loss

                        exit_reason = "SL_HIT"

                        closed = True

                    elif pos.take_profit is not None and tick.bid >= pos.take_profit:

                        exit_price = pos.take_profit

                        exit_reason = "TP_HIT"

                        closed = True

                elif pos.side == "SELL":

                    if pos.stop_loss is not None and tick.ask >= pos.stop_loss:

                        exit_price = pos.stop_loss

                        exit_reason = "SL_HIT"

                        closed = True

                    elif pos.take_profit is not None and tick.ask <= pos.take_profit:

                        exit_price = pos.take_profit

                        exit_reason = "TP_HIT"

                        closed = True



                if closed and exit_price is not None:

                    pos.exit_time = tick.tick_time

                    pos.exit_price = exit_price

                    pos.exit_reason = exit_reason



                    if pos.side == "BUY":

                        diff = exit_price - pos.entry_price

                    else:

                        diff = pos.entry_price - exit_price



                    gross_pnl = diff * self._config.contract_size * pos.volume_lots

                    net_pnl = gross_pnl - pos.commission_usd

                    pos.realized_pnl_usd = net_pnl



                    balance += net_pnl

                    completed_trades.append(pos)

                else:

                    still_open.append(pos)



            open_positions = still_open



            # 2. Track floating equity and drawdown

            floating_pnl = Decimal("0.00")

            for pos in open_positions:

                if pos.side == "BUY":

                    diff = tick.bid - pos.entry_price

                else:

                    diff = pos.entry_price - tick.ask

                floating_pnl += diff * self._config.contract_size * pos.volume_lots



            current_equity = balance + floating_pnl

            if current_equity > peak_equity:

                peak_equity = current_equity



            dd = peak_equity - current_equity

            if dd > max_drawdown_usd:

                max_drawdown_usd = dd

                if peak_equity > Decimal("0"):

                    max_drawdown_pct = (dd / peak_equity) * Decimal("100")



            # 3. Feed tick into BarBuilder

            new_closed_bar = self._bar_builder.process_tick(tick)

            if new_closed_bar is not None:

                closed_bars.append(new_closed_bar)



                # Evaluate Brain pipeline on CLOSED bars only

                candidate = self._brain_pipeline.process(

                    latest_tick=tick,

                    closed_bars=closed_bars,

                    news_state="CLEAR",

                )



                if candidate is not None and candidate.direction != SignalDirection.NONE:

                    # 4. Evaluate through RiskEngine

                    snapshot = AccountRiskSnapshot(

                        account_id="backtest_account",

                        current_balance_usd=balance,

                        current_equity_usd=current_equity,

                        equity_peak_usd=peak_equity,

                        daily_realized_pnl_usd=balance - self._config.initial_balance_usd,

                        daily_floating_pnl_usd=floating_pnl,

                        open_position_count=len(open_positions),

                        snapshot_at=tick.tick_time,

                        open_lot_exposure=sum((p.volume_lots for p in open_positions), Decimal("0")),

                    )



                    market_cond = MarketCondition(

                        symbol=tick.symbol,

                        bid=tick.bid,

                        ask=tick.ask,

                        tick_timestamp=tick.tick_time,

                        spread=tick.ask - tick.bid,

                        market_data_status="READY",

                    )



                    decision = self._risk_engine.evaluate(

                        snapshot=snapshot,

                        candidate_signal=candidate,

                        market_condition=market_cond,

                        news_state="CLEAR",

                    )



                    if decision.trading_allowed and decision.authorized_lot_size:

                        lots = decision.authorized_lot_size

                        slippage = Decimal(str(self._config.slippage_points)) * self._config.point_value

                        if candidate.direction == SignalDirection.BUY:

                            entry_px = tick.ask + slippage

                            side_str = "BUY"

                        else:

                            entry_px = tick.bid - slippage

                            side_str = "SELL"



                        comm = self._config.commission_per_lot_usd * lots * Decimal("2")

                        trade = BacktestTrade(

                            trade_id=str(uuid.uuid4()),

                            symbol=tick.symbol,

                            side=side_str,

                            entry_time=tick.tick_time,

                            entry_price=entry_px,

                            volume_lots=lots,

                            stop_loss=candidate.suggested_stop_loss,

                            take_profit=candidate.suggested_take_profit,

                            commission_usd=comm,

                        )

                        open_positions.append(trade)



        # Close any remaining open positions at final tick market price

        if ticks and open_positions:

            final_tick = ticks[-1]

            for pos in open_positions:

                pos.exit_time = final_tick.tick_time

                if pos.side == "BUY":

                    exit_price = final_tick.bid

                    diff = exit_price - pos.entry_price

                else:

                    exit_price = final_tick.ask

                    diff = pos.entry_price - exit_price



                pos.exit_price = exit_price

                pos.exit_reason = "END_OF_DATA"

                gross_pnl = diff * self._config.contract_size * pos.volume_lots

                net_pnl = gross_pnl - pos.commission_usd

                pos.realized_pnl_usd = net_pnl

                balance += net_pnl

                completed_trades.append(pos)



        # 5. Compute summary statistics

        total_trades = len(completed_trades)

        wins = [t for t in completed_trades if t.realized_pnl_usd > Decimal("0")]

        losses = [t for t in completed_trades if t.realized_pnl_usd < Decimal("0")]

        winning_count = len(wins)

        losing_count = len(losses)



        win_rate = (

            (Decimal(str(winning_count)) / Decimal(str(total_trades))) * Decimal("100")

            if total_trades > 0

            else Decimal("0.00")

        )



        gross_profit = sum((t.realized_pnl_usd for t in wins), Decimal("0"))

        gross_loss = abs(sum((t.realized_pnl_usd for t in losses), Decimal("0")))



        profit_factor = (

            gross_profit / gross_loss

            if gross_loss > Decimal("0")

            else None

        )



        total_net_pnl = balance - self._config.initial_balance_usd

        expectancy = (total_net_pnl / Decimal(str(total_trades))) if total_trades > 0 else Decimal("0.00")

        largest_win = max((t.realized_pnl_usd for t in wins), default=Decimal("0.00"))

        largest_loss = min((t.realized_pnl_usd for t in losses), default=Decimal("0.00"))



        # Compute consecutive wins and losses

        max_c_wins = 0

        max_c_losses = 0

        cur_wins = 0

        cur_losses = 0

        for t in completed_trades:

            if t.realized_pnl_usd > Decimal("0"):

                cur_wins += 1

                cur_losses = 0

                if cur_wins > max_c_wins:

                    max_c_wins = cur_wins

            elif t.realized_pnl_usd < Decimal("0"):

                cur_losses += 1

                cur_wins = 0

                if cur_losses > max_c_losses:

                    max_c_losses = cur_losses

            else:

                cur_wins = 0

                cur_losses = 0



        return BacktestResult(

            initial_balance_usd=self._config.initial_balance_usd,

            final_balance_usd=balance,

            total_net_pnl_usd=total_net_pnl,

            total_trades=total_trades,

            winning_trades=winning_count,

            losing_trades=losing_count,

            win_rate_pct=win_rate.quantize(Decimal("0.01")),

            profit_factor=profit_factor.quantize(Decimal("0.01")) if profit_factor else None,

            max_drawdown_usd=max_drawdown_usd.quantize(Decimal("0.01")),

            max_drawdown_pct=max_drawdown_pct.quantize(Decimal("0.01")),

            trades=completed_trades,

            gross_profit_usd=gross_profit.quantize(Decimal("0.01")),

            gross_loss_usd=gross_loss.quantize(Decimal("0.01")),

            expectancy_usd=expectancy.quantize(Decimal("0.01")),

            largest_win_usd=largest_win.quantize(Decimal("0.01")),

            largest_loss_usd=largest_loss.quantize(Decimal("0.01")),

            consecutive_wins=max_c_wins,

            consecutive_losses=max_c_losses,

        )



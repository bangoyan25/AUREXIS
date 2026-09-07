"""
Reconciliation engine skeleton — TASK-305.

Performs periodic comparison between server-tracked state and MT5/broker state:
1. Compares open positions in PostgreSQL with positions reported by MT5 EA.
2. Detects:
   - ORPHAN: Position exists in MT5 but not tracked in server DB.
   - PHANTOM: Position exists in server DB but closed on MT5.
   - MISMATCH: Volume or side differs between server DB and MT5.
3. Fail-safe policy:
   - On MISMATCH or ORPHAN: Log CRITICAL audit alert, block new trade entries for that account.
   - Do NOT automatically close orphan positions without explicit confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.execution.reports import PositionReport

logger = get_logger("execution.reconciliation")

DiscrepancyType = Literal["MATCH", "ORPHAN", "PHANTOM", "VOLUME_MISMATCH", "SIDE_MISMATCH"]


@dataclass(frozen=True)
class Discrepancy:
    """A single reconciliation divergence between server and MT5."""
    account_id: str
    broker_ticket: int
    discrepancy_type: DiscrepancyType
    server_volume: Decimal | None
    broker_volume: Decimal | None
    detail: str


@dataclass(frozen=True)
class ReconciliationResult:
    """Outcome of a reconciliation cycle for an account."""
    account_id: str
    reconciled_at: datetime
    is_clean: bool
    matched_count: int
    discrepancies: list[Discrepancy]

    @property
    def has_critical_discrepancy(self) -> bool:
        """True if any discrepancy requires halting new trades."""
        critical = {"ORPHAN", "VOLUME_MISMATCH", "SIDE_MISMATCH"}
        return any(d.discrepancy_type in critical for d in self.discrepancies)


class ReconciliationEngine:
    """
    Compares server positions against broker position reports.
    Pure functional evaluation: returns ReconciliationResult without side-effects.
    """

    def reconcile(
        self,
        account_id: str,
        server_positions: dict[int, dict[str, object]],  # ticket → position dict
        broker_positions: list[PositionReport],
    ) -> ReconciliationResult:
        """
        Reconcile server positions against broker positions.

        server_positions: dict keyed by broker_ticket (int)
        broker_positions: list of PositionReport from MT5 EA
        """
        discrepancies: list[Discrepancy] = []
        matched_count = 0
        broker_tickets_seen: set[int] = set()

        for bp in broker_positions:
            broker_tickets_seen.add(bp.broker_ticket)
            sp = server_positions.get(bp.broker_ticket)

            if sp is None:
                discrepancies.append(
                    Discrepancy(
                        account_id=account_id,
                        broker_ticket=bp.broker_ticket,
                        discrepancy_type="ORPHAN",
                        server_volume=None,
                        broker_volume=bp.lots,
                        detail=(
                            f"Position ticket {bp.broker_ticket} exists on broker "
                            f"({bp.side} {bp.lots} {bp.symbol}) but is NOT tracked in DB."
                        ),
                    )
                )
            else:
                sp_lots = Decimal(str(sp.get("lots", 0)))
                sp_side = str(sp.get("side", ""))
                if sp_lots != bp.lots:
                    discrepancies.append(
                        Discrepancy(
                            account_id=account_id,
                            broker_ticket=bp.broker_ticket,
                            discrepancy_type="VOLUME_MISMATCH",
                            server_volume=sp_lots,
                            broker_volume=bp.lots,
                            detail=f"Volume mismatch: DB={sp_lots}, broker={bp.lots}.",
                        )
                    )
                elif sp_side != bp.side:
                    discrepancies.append(
                        Discrepancy(
                            account_id=account_id,
                            broker_ticket=bp.broker_ticket,
                            discrepancy_type="SIDE_MISMATCH",
                            server_volume=sp_lots,
                            broker_volume=bp.lots,
                            detail=f"Side mismatch: DB={sp_side}, broker={bp.side}.",
                        )
                    )
                else:
                    matched_count += 1

        # Check for phantom positions (in server DB, but not on broker)
        for ticket, sp in server_positions.items():
            if ticket not in broker_tickets_seen and sp.get("status") == "OPEN":
                discrepancies.append(
                    Discrepancy(
                        account_id=account_id,
                        broker_ticket=ticket,
                        discrepancy_type="PHANTOM",
                        server_volume=Decimal(str(sp.get("lots", 0))),
                        broker_volume=None,
                        detail=f"Position ticket {ticket} marked OPEN in DB, but not on broker.",
                    )
                )

        is_clean = len(discrepancies) == 0
        return ReconciliationResult(
            account_id=account_id,
            reconciled_at=datetime.now(UTC),
            is_clean=is_clean,
            matched_count=matched_count,
            discrepancies=discrepancies,
        )

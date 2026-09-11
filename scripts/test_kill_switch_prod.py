"""Kill switch validation test — runs on production VPS."""
import asyncio
import uuid

from sqlalchemy import select

from backend.db.models.risk import RiskConfiguration
from backend.db.models.strategy import StrategyEngineState
from backend.db.session import AsyncSessionLocal
from backend.services.risk_gate import evaluate_risk_gate

ACCOUNT_ID_STR = "26597c4f-19a0-41d3-85f7-ae6197cc31fb"


async def test_kill_switch() -> None:
    acct_id = uuid.UUID(ACCOUNT_ID_STR)

    # 1. Baseline risk gate
    async with AsyncSessionLocal() as session:
        rg1 = await evaluate_risk_gate(session, acct_id)
    print(f"1. Baseline Risk Gate: {rg1.decision} / {rg1.reason_code}")

    # 2. Arm kill switch
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(RiskConfiguration)
            .where(RiskConfiguration.account_id == acct_id)
            .order_by(RiskConfiguration.version.desc())
            .limit(1)
        )
        cfg = res.scalar_one_or_none()
        if cfg is None:
            import datetime

            cfg = RiskConfiguration(
                account_id=acct_id,
                version=1,
                effective_from=datetime.datetime.now(datetime.timezone.utc),
                kill_switch_active=True,
            )
            session.add(cfg)
        else:
            cfg.kill_switch_active = True
        await session.commit()
    print("2. Kill switch ARMED")

    # 3. Verify BLOCK
    async with AsyncSessionLocal() as session:
        rg2 = await evaluate_risk_gate(session, acct_id)
    print(f"3. Risk Gate with KS: {rg2.decision} / {rg2.reason_code}")
    assert rg2.decision == "BLOCK", f"Expected BLOCK got {rg2.decision}"
    assert rg2.reason_code == "KILL_SWITCH_ACTIVE", f"Expected KILL_SWITCH_ACTIVE got {rg2.reason_code}"

    # 4. Disarm kill switch
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(RiskConfiguration)
            .where(RiskConfiguration.account_id == acct_id)
            .order_by(RiskConfiguration.version.desc())
            .limit(1)
        )
        cfg = res.scalar_one()
        cfg.kill_switch_active = False
        await session.commit()
    print("4. Kill switch DISARMED")

    # 5. Verify restored to non-kill-switch state (agent offline is expected here)
    async with AsyncSessionLocal() as session:
        rg3 = await evaluate_risk_gate(session, acct_id)
    print(f"5. Risk Gate after disarm: {rg3.decision} / {rg3.reason_code}")
    assert rg3.reason_code != "KILL_SWITCH_ACTIVE", f"Kill switch should be disarmed, got {rg3.reason_code}"
    print(f"5. Kill switch no longer active. Current block reason: {rg3.reason_code}")

    # 6. Verify strategy is still disabled (no auto-resume)
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(StrategyEngineState)
            .where(StrategyEngineState.account_id == acct_id)
            .limit(1)
        )
        state = res.scalar_one_or_none()
    if state:
        print(f"6. Strategy state after KS disarm: enabled={state.enabled}")
        assert not state.enabled, "Strategy must NOT auto-resume after KS disarm"
        print("6. Strategy correctly remains DISABLED after KS disarm.")
    else:
        print("6. No strategy state found in DB (never enabled) — acceptable.")

    print("\nALL KILL SWITCH CHECKS PASSED.")


if __name__ == "__main__":
    asyncio.run(test_kill_switch())

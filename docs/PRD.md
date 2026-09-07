# AUREXIS Product Requirements Document

## 1. Product vision

AUREXIS is a centralized trading platform where market analysis, strategy logic, risk management, account management and monitoring live on the server, while MT5 acts as the broker-facing execution agent.

## 2. Initial trading scope

- XAUUSD only
- HFM as initial broker target
- One test account first
- Architecture must support multiple accounts (5+ target)
- Tick-by-tick market processing
- The system may issue commands whenever a valid opportunity exists; reaching a profit milestone does not automatically terminate trading.

## 3. Risk-first philosophy

The primary objective is controlled risk, not a guaranteed daily profit.

Daily profit targets are treated as optional goals/observations, not promises.

The system must implement a dynamic profit-protection concept. Example decisions already discussed include:
- after a +$10 equity gain, continued trading remains possible;
- a subsequent -$3 drawdown from the protected reference can trigger a stop;
- if the protected peak reaches +$20, the protection level can move to -$6;
- the exact generalized formula and edge cases must be specified in `docs/RISK_ENGINE.md` before implementation.

Do not hard-code examples as universal rules until the generalized rule is explicitly approved.

## 4. Dashboard

The dashboard should support:
- account selector
- balance/equity
- normalized USD PNL
- optional IDR conversion using the applicable USD/IDR rate
- open positions
- trade history
- risk state
- system/MT5 connectivity
- trading calendar
- daily PNL by account and date

## 5. News protection

The system should support a configurable no-new-entry window before and after high-impact news events. Exact event source, impact mapping and default windows must be specified before production implementation.

## 6. Multi-account

Account isolation is mandatory. A command, position, risk state or PNL record must never be accidentally associated with another account.

## 7. Non-goals

- Guaranteed returns
- Unlimited risk
- Server-side risk bypass by MT5
- Secret credentials inside source code

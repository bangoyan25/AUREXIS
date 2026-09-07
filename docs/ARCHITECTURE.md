# AUREXIS Architecture

## Logical components

- Frontend: Next.js + TypeScript
- Backend/API: Python + FastAPI
- Brain: Python
- Risk Engine: isolated business module/service
- Execution Engine: server-side command orchestration
- PostgreSQL: durable source of truth
- Redis: cache/state/streaming primitives
- MT5 EA: MQL5 execution agent
- Linux VPS: web/backend/brain/database services
- Windows VPS: MT5 execution environment

## Data flow

Market tick
-> market-data normalization
-> market state
-> Brain
-> candidate signal
-> Risk Engine
-> approved/rejected
-> command
-> MT5
-> broker
-> execution event
-> reconciliation
-> PostgreSQL
-> WebSocket
-> dashboard

## Separation of concerns

Trading analysis must not be duplicated between server Brain and MT5 EA.

Risk decisions must not be bypassable by frontend or MT5.

Frontend is a presentation/control surface, not a source of trading truth.

## Initial deployment

Start with one account and the smallest reliable infrastructure that can run the complete end-to-end path. Scale only after correctness, observability and failure handling are demonstrated.

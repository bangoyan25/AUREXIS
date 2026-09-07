# AUREXIS Deployment

## Initial topology

Linux VPS:
- frontend
- backend/API
- Brain
- PostgreSQL
- Redis
- reverse proxy

Windows VPS:
- MT5 terminal
- AUREXIS MT5 EA

## Domain

Domain choice is fixed conceptually but the actual domain is intentionally stored outside source/spec files until provisioned.

## Environments

- local
- staging
- production

Production deployment must not be the first environment used for trading validation.

## Backups

PostgreSQL backups, configuration backups and recovery testing are required before live deployment.

## Monitoring

At minimum:
- service health
- database health
- Redis health
- MT5 heartbeat
- market-data freshness
- command latency
- command failures
- reconciliation mismatches
- risk state

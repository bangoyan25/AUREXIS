# AUREXIS Security

## Secrets

Never commit:
- passwords
- API keys
- broker credentials
- private keys
- JWT secrets
- encryption keys

Use `.env` locally and a dedicated secret-management approach in production.

## Trading credentials

Prefer isolating broker credentials to the MT5 execution environment. The Brain should not need plaintext broker passwords for normal operation.

## Access control

Implement least privilege for:
- users
- services
- database roles
- MT5 agents

## Audit

Security-sensitive actions and trading control actions must be auditable.

## AI coding rule

Never paste production secrets into an AI coding prompt.

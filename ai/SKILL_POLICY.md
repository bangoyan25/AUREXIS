# AUREXIS SKILL POLICY

## Purpose

This file defines how installed Claude skills may be used inside AUREXIS.

Skills are implementation aids. They are NOT product authority.

## Authority hierarchy

When instructions conflict, use this priority:

1. `docs/MASTER_SPECIFICATION.md`
2. `ai/DO_NOT_CHANGE.md`
3. Security and risk-safety requirements
4. Detailed `docs/` specifications
5. Approved ADRs / change requests
6. Task acceptance criteria
7. Installed skills
8. Existing implementation
9. Agent preference

An installed skill must never override a locked AUREXIS requirement.

## Current skills

### no-ai-slop

Use for:
- documentation quality;
- concise technical communication;
- README/content quality;
- avoiding generic AI-generated prose.

Do not let it change technical requirements.

### UI/UX Pro Max

Use for:
- dashboard design;
- visual hierarchy;
- UX flows;
- responsive layouts;
- data visualization;
- design systems.

It must not alter:
- backend authority;
- security;
- trading logic;
- risk rules;
- API contracts without approval.

### Ponytail

Use for:
- YAGNI;
- reducing unnecessary abstractions;
- minimizing dependencies;
- avoiding premature complexity;
- preferring simple implementations.

IMPORTANT:

"Simpler" does NOT mean removing safety-critical architecture.

Never remove or bypass:
- Risk Engine;
- reconciliation;
- idempotency;
- account isolation;
- auditability;
- authentication;
- authorization;
- failure-safe behavior;
- required observability.

### unslop

Use primarily for:
- human-readable documentation;
- reducing repetitive AI phrasing;
- improving explanations.

Do not apply it in a way that changes:
- source code semantics;
- API payloads;
- database contracts;
- error codes;
- logs that require machine parsing;
- trading rules.

## Conflict examples

If Ponytail recommends removing reconciliation because it appears complex:

REJECT the recommendation.

If UI/UX Pro Max recommends storing trading state only in browser state:

REJECT the recommendation.

If no-ai-slop recommends rewriting a technical specification and the rewrite changes meaning:

REJECT the rewrite.

If a skill suggests a useful improvement that changes a locked requirement:

Create a change request instead of silently applying it.

## Principle

Skills improve implementation quality.

They do not define what AUREXIS is.

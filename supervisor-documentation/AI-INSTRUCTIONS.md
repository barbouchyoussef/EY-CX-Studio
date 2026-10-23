# AI Instructions: EY CX Studio

## 1. Purpose

This file defines how AI assistants and AI-powered features should be used in EY CX Studio development and operation.

## 2. Product AI Principles

- AI assists consultants; it does not replace consultant judgment.
- Generated outputs must be reviewable.
- Numeric claims must come from deterministic backend calculations.
- Source evidence and uncertainty should remain visible.
- Sensitive client data must be handled according to approved provider and tracing policies.

## 3. Development Instructions for AI Assistants

When working on this repository:

1. Read `README.md` first for setup and product overview.
2. Read `DEEPDIVE.md` for implementation paths.
3. Read the relevant feature file in `docs/architecture/`.
4. Keep changes scoped to the requested area.
5. Do not bypass the LLM gateway for model calls.
6. Do not add schema changes without migrations.
7. Do not weaken authentication or authorization behavior.
8. Do not commit secrets, `.env`, uploaded files, or runtime artifacts.
9. Add or update tests for security, persistence, scoring, extraction, or shared behavior.
10. Update supervisor documentation when product behavior changes.

## 4. Runtime AI Feature Rules

- All LLM calls should go through the shared backend gateway.
- Prompts should receive computed statistics rather than asking the model to compute figures.
- Generated recommendations should be gated by available evidence.
- Model failures should degrade clearly where possible.
- Provider retries and usage logging should remain centralized.

## 5. Prompting Guidelines

- Include the user-selected language.
- Include only relevant evidence.
- Separate instructions from source material.
- Ask for structured JSON only when code validates and parses it.
- Treat malformed model output as recoverable input when possible.
- Avoid prompting the model to invent missing facts.

## 6. Review Requirements

Before client-facing use:

- Consultant reviews generated reports.
- Metrics are checked against computed source data.
- Recommendations are checked for evidence support.
- Sensitive prompts and outputs are handled according to provider policy.

## 7. Prohibited AI Behaviors

- Direct provider calls outside the gateway.
- Model-generated numbers presented as computed facts.
- Hidden use of client content in tracing tools without approval.
- Using LLM output to bypass access-control checks.
- Treating generated content as final without review.

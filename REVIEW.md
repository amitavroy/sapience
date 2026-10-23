# Review checklist

Used by the `reviewer` subagent and by humans. Review the diff against the stated intent (ticket, plan task or request). Report findings most severe first, each with `file:line`, what is wrong and a concrete failure scenario. Separate **must fix** from **nit**. If nothing is wrong, say so.

## 1. Intent

- Does the change do what was asked, no more and no less? Flag missing pieces and scope creep (extra features, unrelated refactors, drive-by edits).
- Does it match the plan's design, or does it deviate? A deviation is fine if it is stated and justified; silent drift is not.
- Is the plan's checkbox/docs updated when the task says so?

## 2. Correctness

- Logic errors, off-by-one, wrong status codes, unhandled `None`, error paths that swallow exceptions.
- Retries and idempotency: is a retry safe? Can a duplicate delivery (Celery is at-least-once, Google retries events) double-post or double-write?
- Races: lock/queue/transaction ordering, check-then-act.
- Data: cascades, uniqueness, migrations that match the models, downgrade works.

## 3. Project rules (`docs/architecture/index.md`)

- Persistence only in `app/services/`; no queries or commits in routes, tasks, deps or the CLI. Services never open their own session.
- Async everywhere I/O happens. A blocking or CPU-heavy call inside `async def` without `SYNC-EXCEPTION` and isolation is a defect. A plain `def` route is not.
- No DB session held across slow network work.
- Outbound calls have an explicit timeout and a retry policy.
- New settings are in both `config.py` and `.env.example`.

## 4. Tests

- Does each test fail if the behavior it claims is broken? Flag tests that assert nothing meaningful or only the happy path.
- Failure paths covered: bad input, external error, empty/blank values, boundaries (limits at N and N+1).
- No real network, LLM, Google or Redis. Fakes behave like the real thing where it matters.
- Anything the SQLite test DB cannot prove is called out, not silently assumed.

## 5. Security and safety

- Secrets, tokens, keys or personal data in code, logs, fixtures or error messages.
- Input validation at the boundary; auth required where it should be; identity taken from verified data, not from user-controlled fields or from the LLM.
- LLM output treated as untrusted (length caps, no instructions followed from retrieved content, tools cannot choose whose data they read).

## 6. Maintainability

- Reads like the surrounding code: naming, comment density, structure. Comments explain why.
- No dead code, duplicated helpers, or speculative abstraction.
- Docs in `docs/wiki/` and `docs/architecture/adr.md` updated when behavior or a decision changed. Limits and magic numbers have one source of truth.

## Not worth raising

Formatting and import order (ruff and the Stop hook own it), personal style preferences, and renames with no clarity gain.

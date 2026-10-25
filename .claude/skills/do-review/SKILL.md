---
name: do-review
description: Review the current changes against a plan (or ticket/request) and the project's architecture docs. Language-agnostic; adapts to the stack it finds. Read-only, reports findings.
disable-model-invocation: true
---

Review the working tree against a plan and the project's rules. You report; you do not edit, stage, commit or install anything.

## Step 1 — Get the intent

The argument names the plan: a number or slug under `docs/plans/` (resolve it the same way `/do-work` does), or a path. If it names a GitHub issue or free text instead, use that as the intent. If there is no argument, ask for one; do not guess.

Read the whole plan: the To-do table, Context, Decisions, files to change, Testing plan, Verification. Work out which task(s) the diff is meant to cover: the rows ticked `[x]` that the diff touches, or the single task the user names. Judge the diff against those, not against the whole plan.

## Step 2 — Learn the project

Do not assume a language or framework. Detect it:

- Read `CLAUDE.md`/`AGENTS.md`/`README.md` for commands and conventions, then identify the stack from manifests (`pyproject.toml`, `package.json`, `composer.json`, `go.mod`, `Cargo.toml`, ...) and the layout of the source tree.
- Read `docs/architecture/index.md` in full. Follow its links and read the other architecture docs the diff plausibly touches (e.g. `docs/architecture/adr.md`, data, security, testing). Read `REVIEW.md` if it exists and use it as the checklist.
- Apply the stack's own idioms when judging: async misuse in Python/JS, N+1 queries or mass assignment in PHP/Laravel, unhandled promises in JS, and so on. Use only checks that apply to what you found.

## Step 3 — Read the change

- `git status` and `git diff HEAD`. Files marked `??` are new and absent from the diff: read them in full.
- Read the files the diff touches in full where needed, plus callers and sibling files, to check conventions.
- Do not run tests, formatters or installs. You may read their last known state only if the user gives it.

## Step 4 — Judge

1. **Intent:** does it do what the task asks, no more and no less? Missing pieces, scope creep, silent deviation from the plan's Decisions. Is the plan checkbox and any doc the task requires (wiki, ADR, API collection) updated?
2. **Architecture rules:** every rule in the architecture docs that the diff could break, quoted by name (e.g. "Persistence lives in services"). A rule the docs state as a defect is a must-fix.
3. **Correctness:** logic errors, unhandled empty/null cases, swallowed errors, retries and idempotency, races, data integrity and migrations matching models.
4. **Tests:** present for the behavior and its failure paths, and actually asserting the claim. Compare against the plan's Testing plan. If the task defers tests to a later row, do not flag their absence.
5. **Security and config:** secrets, missing validation, unsafe input, settings added to every place the project requires.
6. **Conventions:** naming, comment density and idiom match neighbouring code.

Verify before claiming: a finding needs a concrete failure scenario you traced in the code, not a hunch. Drop anything you cannot trace.

## Step 5 — Report

Findings most severe first, split into **Must fix** and **Nits**. Each: `file:line`, what is wrong, a concrete failure scenario, and the rule or plan line it breaks when there is one. Then one line on whether the diff matches the plan task. If nothing is wrong, say so plainly. Do not pad, and do not fix anything; the user decides what to act on.

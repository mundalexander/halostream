# Copilot instructions for HaloStream

This repository is a local AI model operations and benchmarking workspace for the HaloStream project. Treat it as an engineering repo focused on running GLM-5.3-Flash and related inference workloads on a Strix Halo / AMD platform.

## Goals

- Keep the project grounded in the actual runbook in PLAN.md.
- Favor small, incremental, maintainable changes.
- Respect the operational caution around large model downloads and runtime validation.

## Always check first

Before making a change, inspect the relevant files from this list in priority order:
1. README.md
2. PLAN.md
3. docs/ relevant files
4. scripts/ or patch files that relate to the task

## Operational safety

- Do not trigger or suggest large model downloads without explicit confirmation.
- Do not claim GPU success unless the docs or logs show a verified runtime result.
- Keep benchmark outputs in docs/ and label them with date, command, and result.

## Preferred implementation style

- Keep code readable and direct.
- Prefer existing project patterns over introducing new abstractions.
- Shell scripts should log clearly and fail clearly.
- Python code should be deterministic and avoid heavy dependencies unless necessary.

## Completion expectations

When you finish a fix or implementation, report:
- what changed
- why it matches the repo’s goals
- what was verified and with which command

If a task is blocked by missing model availability or unresolved runtime validation, say so explicitly instead of guessing.

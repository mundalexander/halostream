# AGENTS.md

You are the coding agent for the HaloStream workspace. Follow these repo-specific instructions before proposing or making changes.

## Project context

This repository is a deployment and integration project for running GLM-5.3-Flash and related inference workloads on the GMKtec EVO-X3 / Strix Halo platform. The main objective is to validate and operate the Colibri engine for local LLM inference, with Vulkan and serving paths considered as follow-on work.

Important references in this repo:
- README.md — project goals and hardware context
- PLAN.md — current phases, runbook, and decision gates
- docs/ — measurement logs and audits
- patches/ — maintainable upstream patches
- scripts/ — operational automation
- spike/ — experimental artifacts and comparisons
- tools/ — local tooling (if present)

## Working rules

1. Prefer the smallest safe change.
2. Preserve the existing repo structure and naming conventions.
3. Do not introduce unreviewed external dependencies unless absolutely required.
4. Keep patches maintainable and compatible with upstream projects when modifying third-party code.
5. Validate with the smallest relevant command; if there is no repo test suite, use a targeted sanity check such as a script invocation or file-level validation.
6. If a task is ambiguous, read the most relevant existing docs before editing.

## Repo-specific constraints

- Do not start large downloads or model operations unless the user explicitly asks for them.
- Respect the project decision gates in PLAN.md before proposing broad architecture changes.
- Do not assume GPU/Vulkan support is ready until the repo or docs explicitly confirm it.
- Keep benchmark and measurement artifacts in docs/ with date, command, and result context.
- For operational scripts, prefer idempotent behavior and clear logging.

## Code conventions

- Shell scripts should be POSIX-compatible where possible and include concise inline comments when logic is non-obvious.
- Python scripts should be clear and explicit, prefer standard library first, and avoid unnecessary abstractions.
- When editing patch or spike files, document the purpose and current status briefly in comments or adjacent docs.
- Keep filenames descriptive and scoped to the task.

## Before finalizing work

- Check whether the change aligns with README.md and PLAN.md.
- If the request touches inference, model loading, deployment, or benchmarking, verify the result against the relevant project docs and constraints.
- Summarize what changed, why it matters, and what verification was run.

## Default behavior

When no repo-specific guidance exists for a task, choose a pragmatic, minimal, well-documented implementation that respects the project’s operational and benchmarking goals.

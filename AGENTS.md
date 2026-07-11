# claude-forge Codex Guidance

This repository contains reusable agent skills. When working here with Codex, keep changes small, reviewable, and easy to port between agent surfaces.

## PR / Ship Flow

- 2026-07-11: the former "PR creation is Claude-owned / Codex is review-only" boundary was withdrawn. Codex may create branches, commits, pushes, and PRs here.
- Follow the same conventions as Claude Code's ship / create-pr workflows: feature branch (never push to main directly), Japanese commit messages and PR title/body, explicit-path `git add` (no `git add -A`), no force push.
- Never run `gh pr merge`; merge is a human action.

## Review Guidelines

Codex code review should focus on high-signal issues:

- Correctness bugs, edge cases, race conditions, and null/undefined handling.
- Security regressions, auth/authz gaps, secret leakage, unsafe logging, command injection, SSRF, XSS, and unsafe dependency changes.
- Tests that miss important behavior or pass while no longer asserting the intended contract.
- Changes that violate existing repository patterns or make future maintenance materially harder.

Keep review comments specific and actionable. Avoid speculative best-practice comments unless the risk is concrete.

Write all review comments, summaries, and explanations in Japanese (日本語). Keep code identifiers, file paths, commands, and quoted code in their original form (do not translate them).

## Automation Boundary

- GitHub automatic Codex reviews are OFF for this repository (disabled 2026-07-10). Do not post `@codex review` on PRs; review happens locally before push (`/codex:review`).
- Enabling repository-wide Codex automatic reviews is done in Codex GitHub code review settings, not by editing files in this repository.

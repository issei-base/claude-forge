---
name: ship
description: Take current work all the way to a GitHub Pull Request. Creates a feature branch if needed, generates a commit message from the diff, pushes, and opens a PR via `gh`. Trigger when the user asks to ship/submit/finalize work, open or create a PR, or says things like "ship it", "PR出して", "PR作って", "送って", "プルリク", "make a PR", "open a PR", "let's ship this", or otherwise indicates they want the current changes turned into a reviewable PR.
---

# ship

End-to-end "I'm done, turn this into a PR" workflow. Each step has a STOP rule — do not auto-recover from violations, surface them.

## 0. Preflight (all must pass — STOP on failure)

Run in parallel:
- `gh auth status` — must be logged in. If not, tell user to `gh auth login` and STOP.
- `git rev-parse --is-inside-work-tree` — must be true.
- `git remote -v` — must have an `origin` pointing at github.com. If not, ask the user: `gh repo create` now, or abort?
- `git status --porcelain` AND `git log @{u}..HEAD 2>/dev/null` — there must be either uncommitted changes OR unpushed commits. If neither, tell user there is nothing to ship and STOP.

## 1. Branch

- `git branch --show-current` and `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`.
- If on the default branch (main/master/etc.):
  - Look at `git diff` to pick a **kebab-case branch name**, 3-6 words, prefixed by type when obvious: `feat/`, `fix/`, `docs/`, `chore/`, `refactor/`.
  - `git checkout -b <name>`.
- Otherwise: use the current branch.
- Never rename an existing branch.

## 2. Stage

- `git status --porcelain` to see what's modified/untracked.
- Stage **only** files relevant to the change, **by explicit path**. Never `git add -A` / `git add .` — they sweep in `.DS_Store`, accidental logs, IDE files.
- If you see any of these in the unstaged list, STOP and ask the user before staging: `.env*`, `*.pem`, `*.key`, `credentials*`, `id_rsa*`, anything that looks like a token or secret.
- If the user has unrelated changes mixed in, ask which to include rather than guessing.

## 3. Commit (skip if there are only unpushed commits to ship)

Generate a message from the **staged diff**:
- **Subject:** ≤72 chars, imperative mood ("Add X", not "Added X" / "Adds X"), no trailing period.
- **Body:** optional. 1-3 short sentences on the *why* if it isn't obvious from the diff. Skip the body for trivial changes.
- Show the user the proposed message **before** committing. Offer to edit.
- Commit via HEREDOC to preserve formatting:
  ```sh
  git commit -m "$(cat <<'EOF'
  <subject>

  <body if any>
  EOF
  )"
  ```
- If pre-commit hooks fail: fix the underlying issue, re-stage, create a **new** commit. Do NOT `--amend` or `--no-verify`.

## 4. Push

- New branch: `git push -u origin HEAD`.
- Existing branch with upstream: `git push`.
- If push is rejected as non-fast-forward: STOP. Do NOT `--force` or `--force-with-lease` without explicit user confirmation. Show them the rejection and ask.

## 5. PR

- Resolve base branch: `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`.
- Gather context across **all** commits on this branch:
  - `git log <base>..HEAD --pretty=format:'%s%n%n%b'`
  - `git diff <base>...HEAD --stat`
- **Title:** ≤70 chars. Often matches the latest/primary commit subject. If multiple commits, summarize the umbrella change.
- **Body:** use this structure:
  ```
  ## Summary
  - <1-3 bullets, what changed and why>

  ## Test plan
  - [ ] <how to verify>
  ```
- Create with HEREDOC for body formatting:
  ```sh
  gh pr create --base <base> --title "<title>" --body "$(cat <<'EOF'
  ## Summary
  - ...

  ## Test plan
  - [ ] ...
  EOF
  )"
  ```
- If a PR already exists for this branch (`gh pr view` returns one), don't create a duplicate — show the URL and ask if the user wants to update title/body instead.

## 6. Report

- Print the PR URL on its own line (so the terminal makes it clickable).
- Do NOT auto-merge, auto-request reviewers, or push more changes. Stop here.

## Things NOT to do

- No `git push --force` without explicit confirmation, ever.
- No `gh pr merge`. The user decides when to merge.
- No `git commit --amend` to "fix" a failed hook — make a new commit.
- No skipping hooks (`--no-verify`, `--no-gpg-sign`) unless the user explicitly asked.
- No committing `.env`, key files, or anything matching common secret patterns.
- No `git add -A` / `git add .` — always stage by explicit path.

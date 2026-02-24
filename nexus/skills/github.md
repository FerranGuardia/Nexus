---
name: github
description: GitHub operations via gh CLI — issues, PRs, CI, code review, API queries
requires: [gh]
install: brew install gh && gh auth login
---

# GitHub Skill

Use `gh` CLI instead of navigating github.com in a browser.

## When to use

- Checking PR status, reviews, CI runs
- Creating/commenting on issues or PRs
- Listing repos, releases, collaborators
- Querying the GitHub API for any data

## When NOT to use

- Local git operations (commit, push, pull) — use `git` directly
- Cloning repos — use `git clone`

## Safety

Actions visible to others — confirm with user before running:

- `gh pr create` — creates a public PR. Show title + body first.
- `gh issue create` — creates a public issue. Show title + body first.
- `gh issue comment` / `gh pr comment` — posts a comment others see. Show it first.
- `gh pr merge` — merges code. Always confirm.
- `gh pr review --approve` — approves a PR. Always confirm.
- `gh repo delete` — NEVER run this.

Safe to run freely (read-only):
- `gh pr list/view/checks/diff`, `gh issue list/view`, `gh run list/view`, `gh api` (GET)

## Auth

```bash
gh auth status          # check if authenticated
gh auth login           # interactive login (one-time)
```

## Pull Requests

```bash
gh pr list
gh pr view 55
gh pr checks 55                    # CI status
gh pr create --title "feat: X" --body "Description"
gh pr merge 55 --squash
gh pr diff 55
gh pr review 55 --approve
```

## Issues

```bash
gh issue list --state open
gh issue create --title "Bug: X" --body "Details"
gh issue close 42
gh issue comment 42 --body "Fixed in #55"
```

## CI / Workflow Runs

```bash
gh run list --limit 10
gh run view <run-id>
gh run view <run-id> --log-failed  # only failed step logs
gh run rerun <run-id> --failed
```

## API Queries

```bash
gh api repos/owner/repo/pulls/55 --jq '.title, .state'
gh api repos/owner/repo/labels --jq '.[].name'
gh api repos/owner/repo --jq '{stars: .stargazers_count, forks: .forks_count}'
```

## JSON Output

```bash
gh pr list --json number,title,state --jq '.[] | "\(.number): \(.title)"'
gh issue list --json number,title --jq '.[] | select(.title | test("bug"; "i"))'
```

## Tips

- Always specify `--repo owner/repo` when not in a git directory
- Use URLs directly: `gh pr view https://github.com/owner/repo/pull/55`
- Rate limits apply; use `gh api --cache 1h` for repeated queries

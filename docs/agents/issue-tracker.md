# Issue tracker: GitHub

Issues and PRDs for this repo live in GitHub Issues for:

`https://github.com/Moistenxx/windows-.git`

Use the `gh` CLI for issue operations when available.

## Conventions

- Create an issue: `gh issue create --title "..." --body "..."`
- Read an issue: `gh issue view <number> --comments`
- List issues: `gh issue list --state open --json number,title,body,labels,comments`
- Comment on an issue: `gh issue comment <number> --body "..."`
- Apply labels: `gh issue edit <number> --add-label "..."`
- Remove labels: `gh issue edit <number> --remove-label "..."`
- Close an issue: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v` when running inside the clone.

## Pull requests as a triage surface

PRs as a request surface: **no**.

Do not include external PRs in `/triage` unless this file is updated later.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

# AGENTS.md

## Jira Ticket Workflow

When the user asks to tackle one or more Jira tickets, use this flow unless the user explicitly says otherwise:

- Before making code changes, identify every repo that will be touched by the selected Jira tickets.
- In each affected repo, inspect the current branch and working tree before changing branches.
- Pull the latest changes from the repo's default branch, using `main` if it exists and `master` otherwise.
- Create a new feature branch from the freshly updated `main`/`master`; do not start Jira implementation work from a stale branch.
- Use one branch per affected repo for the selected Jira work unless the user explicitly asks for separate branches.
- Keep all work for the selected Jira tickets in a repo on that repo's single branch.
- Commit after meaningful finished steps, but avoid excessive tiny commits; group closely related changes.
- Do not push branches or open PRs until the user says testing is complete or explicitly asks to push/open PRs.
- When ready, push each repo branch and open exactly one PR per repo unless the user explicitly asks for multiple PRs.
- The user will normally merge PRs in GitHub; only merge PRs or resolve merge conflicts when explicitly asked.

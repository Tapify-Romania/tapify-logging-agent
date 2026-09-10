# AGENTS.md

## Workspace Guidance

Before working here, read the containing [Tapify AGENTS.md](../AGENTS.md),
including General Guidelines, Jira Ticket Workflow, Scope and Safety, and
Development and Verification. Resolve that path relative to this file even
when the agent starts at this Git root. This file adds repository-specific
rules; it does not grant changes to sibling repositories.

Make reasonable scoped decisions, implement requested work, and run appropriate
local checks without asking before each ordinary edit or command. Inspect Git
status first, preserve unrelated changes, and review the final diff. Sibling
repositories are read-only references unless the task includes them; read their
instructions before consulting them and do not run state-writing checks there.

If the parent guidance is unavailable in a standalone clone, retain these
boundaries: commits, pushes, PRs, deployments, cloud resources, paid operations,
production changes, destructive actions, live hardware operations, and social
publishing require explicit authorization covering the action. Testing alone
is not approval to commit or publish. Locate the shared workflow before starting
Jira implementation; do not invent a replacement. Tool permissions and sandbox
restrictions still apply.

## Configuration and Operations

Inspect the repository's scripts and configuration to select local syntax and
schema checks; do not assume a Node package manager or application build.
Deployment scripts, Docker service/volume changes, remote host operations, and
production configuration changes require explicit authorization for the target.
Do not print secrets or customer data while validating configuration.

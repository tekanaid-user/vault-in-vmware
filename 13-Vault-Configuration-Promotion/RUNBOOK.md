# Pilot setup and operations

## One-time setup

| Step | Owner | Required result |
| --- | --- | --- |
| 1. Baseline | Sam + Security | Choose one application; review Git paths/fields/policy, AppRole TTLs/use limits, mount settings, intended differences, rotation field and threshold. Do not adopt example defaults blindly. |
| 2. Endpoints | DevOps | Edit each `environments/*/settings.json` with real HTTPS address, namespace if needed and approved scope. Install CA on runner or set `VAULT_CACERT`. |
| 3. Git releases | Sam + reviewers | After configuration is committed, reviewed PRs set full configuration commit SHAs in each `release.yaml`. Start DEV; UAT/PROD may remain at an earlier approved release. |
| 4. Read-only access | Vault administrator | Install the scoped drift policy per Vault. Align paths to the approved mount/prefix and selected policy/AppRole. No secret-data read. |
| 5. OIDC | Vault administrator | Enable/configure JWT at `github` for issuer/discovery `https://token.actions.githubusercontent.com`. Human LDAP access stays as it is. |
| 6. Runners and environments | DevOps | Restricted self-hosted runner labelled `vault-demo`, Python 3.10+, tested Terraform CLI, Vault/backend connectivity. Create the nine GitHub environments below; restrict them to main. Required reviewers on deployment environments, especially PROD. |
| 7. Promotion state | DevOps | Configure separate protected remote state per environment/root; locking, encryption, backups and backend identity. Inventory/import existing policy/AppRole before adoption. Drift does not need Terraform or a state backend. |
| 8. Enable pilot | Repository administrator | Set repository variable `VAULT_AUTOMATION_ENABLED=true` once drift prerequisites are complete. Promotion still requires state/import/approval prerequisites before dispatch. No GitHub secrets are needed. |

Create three roles per environment using `bootstrap/github-role.json.example`. Bind exact repository, ref, workflow and environment subject. Install plan/deploy/drift policies with the same names used in these roles. Bootstrap through an authorized administrator identity; credentials remain local, never in Git.

| Role name pattern | GitHub environment / subject suffix | Policy | `workflow_ref` suffix |
| --- | --- | --- | --- |
| `github-ENV-plan` | `ENV-plan` | `demo-plan` | `.github/workflows/vault-promote.yml@refs/heads/main` |
| `github-ENV-deploy` | `ENV` | `demo-deploy` | `.github/workflows/vault-promote.yml@refs/heads/main` |
| `github-ENV-drift` | `ENV-drift` | `demo-drift` | `.github/workflows/vault-drift.yml@refs/heads/main` |

`ENV` is `dev`, `uat` or `prod`. Full subject example: `repo:tekanaid-user/vault-in-vmware:environment:dev-drift`. Full workflow reference starts `tekanaid-user/vault-in-vmware/`. Verify issued claims and installed Vault support during the pilot. Do not broaden to wildcard repositories or PR refs to solve an authentication error.

## Daily Security operation

| Task | Command / action |
| --- | --- |
| First secret entry | From this folder: `./scripts/create-secret.sh --env dev --approve-environment dev`, after local Vault CLI authentication to the correct target with a named identity. Hidden prompts use the approved Git fields; existing locations are refused. Repeat with each environment’s own values. |
| Existing values | Read/edit through Vault UI; retain second-person checks for client IDs/secrets and coordinate rotations with application owners. Update `password_cycle_date` (or agreed field) as ISO date only after real rotation. |
| Structure change | Review Git first; check the target structure before promoting. A UI change can still occur; adopt it into Git or correct it after review. |
| Configuration promotion | Actions → Vault promotion → select environment. Review plan job before approving apply. Verify predecessor deployment evidence; no automatic DEV/UAT-success enforcement is implemented. |
| Drift review | Actions → Daily Vault structure drift → summary and `vault-drift-comparison` artifact. Scheduled daily at 11:00 UTC; manual runs also available. Red job can mean findings or incomplete evidence; examine the report. |
| Resolve finding | Complete promotion, adopt intended structure into Git, document an exception or correct a mistake. Never delete a path solely because it is extra or apparently unused. |

For local or cron collection, authenticate separately to each Vault through a restricted service identity, then run `vault-drift.sh --env ENV`. Protect output directories and credentials with OS permissions. Combine reports with `vault-drift.sh --compare dev.json uat.json prod.json --fail-on-findings`. No token on the command line or in the crontab.

## Pilot acceptance

| Check | Evidence |
| --- | --- |
| No value exposure | Restricted report/developer identity gets subkeys but 403 on data. Reports omit raw metadata and policy/config content; inspect CI logs/artifacts. |
| Drift visible | Introduce a test-only field/path/policy difference; report identifies it. Remove a permission or collector report; comparison becomes incomplete, not equal. |
| Rotation visible | Test recent, overdue, missing, invalid and future dates. Confirm date reflects real rotation, not merely a KV update. |
| Safe creation | Guided writer creates once and refuses a second write or an existing soft-deleted path. |
| Promotion safe | Import existing resources, review actual per-environment plans, approve apply, verify access and state contains no application values. UI value edits remain usable. |
| Cleanup evidence | Application owners approve candidates using audit-history coverage and retention. No standard KV last-access timestamp is assumed. |

Local tests establish behavior in synthetic Vault dev servers. They do not validate customer infrastructure, GitHub OIDC or UI rendering.

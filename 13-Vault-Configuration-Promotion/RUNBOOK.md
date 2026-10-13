# Environment setup and pilot acceptance

**Reporting first:** use [GETTING-STARTED.md](GETTING-STARTED.md) for Workstream 2 only. Set `VAULT_DRIFT_ENABLED=true` after reporting setup; keep `VAULT_AUTOMATION_ENABLED=false` until deployment prerequisites are ready. The manual onboarding workflow does not require either switch.

**Target: Vault Community Edition, no namespaces.** Each environment has its own Vault endpoint; no namespace header or Terraform namespace is used.

Security's operating interface is [GitHub Actions and Vault UI](README.md#actions-and-daily-workflow). Helpers are internal implementation details.

## One-time setup

| Step | Owner | Required result |
| --- | --- | --- |
| Baseline | Security + implementation lead | Choose one application. Review catalog keys, policy paths, TTL/counts and environment CIDRs; example defaults are not an approved environment baseline. Human LDAP remains. |
| Repository | Repository administrator | Approved private environment repository and report visibility, protected `main`, reviewed PRs. Enable Actions PR creation, restrict workflow write permission to request Action. Bot-created PRs do not trigger other workflows with the default GITHUB_TOKEN; require manually dispatched validation/reviewer evidence before merge. |
| Runner/endpoints | DevOps | Restricted self-hosted runner labelled `vault-demo`; Python 3.10+, Terraform 1.16.1/provider 5.8.0; HTTPS Vault endpoints/CA and state connectivity. Edit `environments/*/settings.json`; install trust or `VAULT_CACERT`. No deployment identities on untrusted PR jobs. |
| State | DevOps | Separate remote `admin-setup` state per environment; encryption, access control, locking and backups. Replace backend placeholders; runner obtains backend identity separately. Imports adopt existing resources, so examine first plan for unwanted configuration/tune changes. Mount type conflicts fail; deletes/replacements are blocked. |
| Vault policies | Vault administrator | Expand `admin-plan-policy.hcl` and `admin-deploy-policy.hcl` for each exact approved application name and `restart` when managed; no value reads. Install drift policy, adapting nested mount permissions. Separate credential policy and restricted delivery readers. |
| OIDC | Vault administrator | JWT auth at `github`; discovery/issuer `https://token.actions.githubusercontent.com`; exact audience, repository ID, owner ID, main ref, environment subject and workflow binding. Use `github-role.json.example` with the roles below. |
| Credential delivery | Vault administrator + Security | Create KV v2 `automation-delivery`; restrict UI readers for `restart/credentials`. Require reviewers for every `ENV-credentials` environment. Set TTL/use limits deliberately and define distribution/revocation; issuance creates an additional credential, not replacement/revocation. |
| Enable/accept | Repository administrator + Security | For reports only, set `VAULT_DRIFT_ENABLED=true` after reporting setup; leave `VAULT_AUTOMATION_ENABLED=false`. Set the broader automation flag only once deployment prerequisites are ready. Reporting requires no Terraform state. |

| OIDC role setting | GitHub environment | Workflow binding |
| --- | --- | --- |
| `admin_plan_role` | `ENV-plan` | `.github/workflows/vault-admin-deploy.yml@refs/heads/main` |
| `admin_deploy_role` | `ENV` | `.github/workflows/vault-admin-deploy.yml@refs/heads/main` |
| `drift_role` | `ENV-drift` | `.github/workflows/vault-drift.yml@refs/heads/main` |
| `credential_role` | `ENV-credentials` | `.github/workflows/vault-restart-credentials.yml@refs/heads/main` |

`ENV` is DEV/UAT/PROD in lowercase. UAT/PROD apply requires independent review after the plan job. Full immutable subject example: `repo:tekanaid-user@37753095/vault-in-vmware@1406319724:environment:dev-plan`. Query the repository's subject customization and IDs; verify actual issued JWT claims. Do not broaden repository or ref bindings. Human GitHub auth is not the machine authentication mechanism.

## Acceptance checklist

| Check | Required evidence |
| --- | --- |
| Request | Security submits application/key/settings form, reviewer examines catalog PR, then release PR pins merged configuration SHA. Reject bad names and unknown/secret-bearing settings. |
| Plan/apply | Existing config imports without duplicate creation; review mount tuning and role/policy changes. Separate-job artifact restoration, integrity checks, reviewer gating and correct-target saved-plan apply. Confirm remote state and recovery. |
| Values | Enter values in Vault UI under approved paths. Check application access; inspect logs/state/artifacts for no values or tokens. Provisioning does not mint SecretIDs. |
| Promotion | Same SHA DEV → UAT → PROD, separate plans and state; reviewer checks predecessor success. No automatic predecessor enforcement. |
| Reports | Restricted scan/developer identity gets subkeys but 403 on data. Introduced path/key/policy drift is visible; missing/denied evidence cannot pass. Agree exceptions, report access and cadence. |
| Rotation | Confirm metadata field and ISO date represents actual password rotation. Recent/overdue/missing/invalid/future cases; 90 days is an example, not policy. |
| Credentials | Protected deliberate issuance; correct delivery CAS version; UI retrieval only for approved readers. Rehearse failed delivery and revocation, without exposing generated SecretIDs. |

## Unused-path evidence

This follow-up has no implemented last-access report. Obtain audit access history and retention/coverage for every relevant Vault, identify old-name candidates, and review with application owners. Record owner, observed window, known scheduled/infrequent usage and migration history. No audit reads in a window is not proof a path is unused. Archive/recover according to an approved cleanup change; never delete solely because it is extra.

## Current example controls

Example environments restrict deployment to main; UAT/PROD have reviewer gates. Main protection and permanent environment runners remain pending. Credential environments require independent review before use. Repository application secrets and stored Vault tokens are not used. The request workflow has narrowly scoped Git contents/PR write permission; other jobs use read and short-lived OIDC identities. [GitHub workflow inputs](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onworkflow_dispatchinputs).

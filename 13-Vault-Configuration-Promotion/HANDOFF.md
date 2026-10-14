# Workstream 2 handoff: first environment run

**Read first:** [GETTING-STARTED.md](GETTING-STARTED.md). It answers where the scripts live, where the Vault URLs go, how to configure OIDC and what Security does in Actions. [Sample report](examples/REPORT-WALKTHROUGH.md).

[LOCAL-LAB.md](LOCAL-LAB.md) provides a reproducible working example. The report is actual local API evidence, with separate real GitHub federation evidence.

## First working session

| Order | Who | Result |
| --- | --- | --- |
| 1 | DevOps + repo administrator | Target repo/default-main workflow, `dev-drift` environment, restricted internal runner with `vault-demo` label, Python/Git and Vault CA trust. |
| 2 | DevOps | Run **Vault drift - getting started**, `dev`, `claims`; download the selected identity claims. No Vault configuration is needed yet. |
| 3 | Vault administrator / Security | Enable JWT auth at `github`, configure the actual GitHub issuer and install the read-only drift policy. Create `github-dev-drift` using the target claims and drift-role template. |
| 4 | DevOps + Security | Review `environments/dev/settings.json`: DEV URL, audience, role and metadata settings. Remove demo inventory expectations/aliases/exceptions. |
| 5 | Security, supported by DevOps | Run `dev`, `authenticate`, then `collect`. Review the artifact's completeness, findings and coverage. |
| 6 | Same teams | Repeat for UAT/PROD under their internal change processes. |
| 7 | Repo administrator + Security | Enable `VAULT_DRIFT_ENABLED=true`, keep `VAULT_AUTOMATION_ENABLED=false`, run **Weekly Vault inventory and rotation**, review the report and agree cadence. |

**Bring to the session:** target repo/GitHub hosting type, three Vault versions/URLs, CA file/trust approach, runner owner/network access, Vault administrator and authorized report readers. No Terraform state bucket is needed for these steps.

## Security's routine after setup

Run **Weekly Vault inventory and rotation** from Actions when needed, or use its schedule. Read the Summary, download `vault-drift-comparison`, classify differences as pending promotion, approved exceptions, mistakes or cleanup candidates, and assign follow-ups. The pipeline does not change Vault.

## What this handoff does not establish

Operators must validate their endpoints, roles and report coverage. Earlier OIDC federation passed against disposable Vaults; the onboarding additions passed local regression checks, while live onboarding still requires environment validation. Workstream 1 deployment/reviewer/backend acceptance remains separate. No live settings or Vaults were changed while preparing this package.

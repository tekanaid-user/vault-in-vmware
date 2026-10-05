# Vault configuration promotion : Terraform Community example

This example shows Terraform-backed policy/configuration promotion and daily DEV/UAT/PROD drift reporting. The recommended initial-secret writer is a planned addition; existing UI reads/value edits remain supported. Security retains Vault UI access. **No application values or stored Vault credentials go into GitHub secrets.**

| Stored in Git | Stored in Vault | Passed to GitHub Actions |
| --- | --- | --- |
| Policies, expected field names, environment settings, release SHAs | Application values | Environment and configuration release |

## Layout and promotion

```text
13-Vault-Configuration-Promotion/
├── configuration/
│   ├── application.json          # Expected path and fields
│   ├── policy.hcl.tftpl
│   ├── configuration/            # Policy + AppRole; separate state
│   └── secret-write/             # Intentional KV writes; separate state
├── environments/{dev,uat,prod}/
│   ├── release.yaml              # Full configuration commit SHA
│   ├── settings.json             # Addresses, roles, overrides; no credentials
│   └── *.backend.hcl             # Remote state locations
├── scripts/                      # Security-facing wrappers and drift collector
├── bootstrap/                    # Example Vault policies and OIDC role
└── workflow-examples/            # Inactive until installed in root .github/workflows
```

| Step | Git action | Deployment |
| --- | --- | --- |
| Create change | Short-lived branch → reviewed PR → main | Select the full immutable configuration SHA |
| DEV | PR updates DEV release reference | Plan/apply DEV; validate application access |
| UAT | PR advances UAT to the same SHA | Review DEV evidence; plan/apply with UAT inputs |
| PROD | PR advances PROD to the same SHA | Review UAT evidence; explicit approval of PROD plan |

Folders contain references and differences, not copied policies. Later main commits do not advance environments. The workflow checks out the selected release for configuration while using reviewed current environment settings. It does not reuse a DEV plan in UAT/PROD.

## Recommended daily workflow: guided creation, UI reads and value edits

| Step | Security does | Actions / Terraform does |
| --- | --- | --- |
| Define | Review Git's path, field names and access policy | Pin the reviewed release SHA |
| DEV | Create with a Git-schema-guided direct writer, supplying DEV values | Check field structure via subkeys; plan/apply policy and AppRole |
| UAT | Create with the same approved schema and UAT values | Promote the same release; check UAT structure and apply configuration |
| PROD | Create with the approved schema and PROD values | Approve the PROD plan; apply configuration |
| Read/edit values | Vault UI | Value-only edits need no Git change; structure changes are reviewed in Git |
| Review | Review daily drift and record intended structural changes in Git | Report differences without changing anything |

**The direct initial-creation writer is not implemented here yet.** For this example’s DEV trial, populate the final path using the Vault UI or an approved CLI/API write before running promotion. The existing scripts implement configuration plan/apply, staging for the optional advanced route, and drift collection.

**Actions knows where to look from `configuration/application.json`.** It uses subkeys to confirm field names without retrieving values. No staging, pipeline value entry or copying DEV credentials into other environments is required. Terraform's default root contains no secret-value resources; values are never part of the default plan/state. UI edits remain available. An extra/missing field blocks the promotion until reviewed, but a value-only change does not.

[Advanced secret-write alternative](ADVANCED-SECRET-WRITES.md) retains the earlier ephemeral/write-only example for a future requirement to have Terraform write values. It is not the recommended daily route.

The repository is currently hosted on GitLab. These inactive GitHub Actions templates are intended for installation in your organization’s GitHub repository; pushing this example to GitLab does not activate them.

## One-time setup : DevOps and Security

| Required setup | Detail |
| --- | --- |
| Terraform and provider | Terraform >=1.11; this example pins Vault provider 5.8.0 and includes generated lock files. Pin a tested Terraform CLI version on runners. |
| Target Vault | Existing KV v2 `secret` mount and `approle` auth; configure real HTTPS addresses/CA. Staging mount is only needed for the optional advanced route. |
| Existing resources | Inventory before applying. Import existing policy/AppRole/KV resources into the appropriate state before adopting them. Do not run the demo against an application without owner approval. |
| Remote state | Replace S3 backend placeholders with approved storage; S3 is an example, not an the organization backend decision. Use encryption, versioning and locking, and separate state keys/credentials per environment/root. Backend credentials come from runner identity or on-prem credential delivery, never GitHub secrets or HCL. |
| Git release reference | Put the full reviewed configuration commit SHA in DEV `release.yaml`; the wrappers require committed configuration, not a moving branch reference. |
| GitHub OIDC | Configure Vault JWT discovery for `https://token.actions.githubusercontent.com`. Create plan/deploy/drift roles per environment from `bootstrap/github-role.json.example`, with exact repository, main ref, workflow and environment claim bindings. Verify claims against your organization’s tokens. |
| Vault permissions | Plan role reads configuration/structure; deploy role writes only policy/AppRole configuration; drift role reads metadata/subkeys/policy. None needs secret-data read access in the default route. Examples are provided; no superuser/root token is used by CI. |
| Runner | Restricted self-hosted `vault-demo` runner with Vault/backend reachability, CA trust, Python 3.10+ and Terraform. No untrusted PR execution on deployment runners. |
| Actions environments | Create dev/uat/prod, plus dev-plan/uat-plan/prod-plan and dev-drift/uat-drift/prod-drift. Required reviewers on apply environments, especially prod; prevent self-review if available on your organization’s GitHub plan. No environment secrets. |
| Workflow installation | Review then copy templates to repository-root `.github/workflows/vault-promote.yml` and `vault-drift.yml`. Change OIDC workflow bindings to these exact paths. Templates are deliberately inactive in this folder. |

For the regular workflows in this example, bind `workflow_ref`; `job_workflow_ref` is specific to reusable workflow calls. Plan/deploy/drift subjects differ because their GitHub environments differ. Example: `repo:ORG/REPO:environment:dev-plan` for DEV planning, `...:environment:dev` for DEV apply.

Initial promotion gates use reviewed release PRs plus GitHub deployment approval. The templates do **not** automatically prove a prior environment's successful rollout: reviewers must check that evidence. Automating predecessor-success checks and merge-triggered dispatch is a subsequent enhancement; this pilot deliberately deploys through manual dispatch.

## Security's daily commands

The proposed initial writer supplies each environment’s own values directly to Vault; subsequent reads/value edits use the UI. Until that writer is implemented, populate this demo’s final path with an approved UI/CLI/API write. Then run the promotion workflow with that environment selected, or use the local wrapper after your existing Vault CLI login:

```bash
./scripts/vault-change.sh plan --env dev --operation configuration
./scripts/vault-change.sh apply --env dev --run <saved-run-path> --approve-environment dev
```

The wrapper selects Vault from environment settings, checks Git-defined structure through subkeys, then plans/applies policy and AppRole configuration only. After DEV validation, update UAT's release pointer by reviewed PR and repeat; then PROD with explicit approval. The workflow's apply job uses a fresh OIDC token and the exact saved plan after reviewer approval. It rejects changed settings/source/plan or mismatched structure.

Local `--approve-environment` records operator intent; it is not independent authorization. Use Actions protected environments or your organization’s change process for PROD. DevOps performs one-time imports into the correct state; the default resource addresses are `vault_policy.application` and `vault_approle_auth_backend_role.application`. The wrapper rejects destructive plans; decommissioning is separate.

## Daily drift report

`vault-drift.yml` collects one report per environment using separate read-only OIDC roles, then combines them. It reads KV metadata and **subkeys**, not secret data. It compares against each environment's selected Git schema/policy as well as against other environments.

```bash
# Authenticate separately to each environment for local collection.
./scripts/vault-drift.sh --env dev > dev.json
./scripts/vault-drift.sh --env uat > uat.json
./scripts/vault-drift.sh --env prod > prod.json
./scripts/vault-drift.sh --compare dev.json uat.json prod.json
```

The pilot scans the `demo/` prefix and selected application policy. Reports include field differences, extra paths, deleted/unknown paths, policy differences and differing release references. Access/network failures remain unknown; equal unknown results are not proof of parity. Differing releases may indicate pending promotion. Security reviews the report and chooses to promote, adopt a UI change into Git, record an exception or correct a mistake. No automatic corrections; value-only edits cannot be detected. AppRole/mount comparison and machine-readable approved exceptions are future additions, not implemented here.

Reports and plan artifacts contain names/configuration and still deserve restricted access. Plan artifacts exclude provider caches, last one day, and contain no application values; review CI logs/artifacts in the DEV pilot before production adoption. Staging cleanup requirements apply only to the optional advanced route.

## Validation performed

Offline Python/shell syntax and CLI help checks; Terraform formatting and `init -backend=false` / `validate`. No Vault login, live plan/apply, staging write, cloud backend initialization or GitHub workflow installation is part of preparing this example. End-to-end DEV validation remains required.

References: [Vault subkeys API](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2#read-secret-subkeys) · [Vault write-only guidance](https://registry.terraform.io/providers/hashicorp/vault/5.8.0/docs/guides/using_write_only_attributes) · [Vault/GitHub OIDC](https://developer.hashicorp.com/validated-patterns/vault/retrieve-vault-secrets-from-github-actions) · [GitHub environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments).

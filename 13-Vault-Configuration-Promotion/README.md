# Vault configuration promotion : Terraform Community example

This example shows Terraform-backed policy/configuration promotion and daily DEV/UAT/PROD drift reporting. A guided create-only initial-secret writer is included; existing UI reads/value edits remain supported. Security retains Vault UI access. **No application values or stored Vault credentials go into GitHub secrets.**

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
├── scripts/                      # Guided writer, inventory/rotation, internal pipeline helper
├── bootstrap/                    # Example Vault policies and OIDC role
├── tests/                        # Unit and local Vault integration tests
└── workflow-examples/            # Reference copies; active workflows in root .github/workflows
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

**Initial writer:** `./scripts/create-secret.sh --env dev --approve-environment dev` reads the pinned Git schema, prompts for values without echo and writes directly to the final Vault path with `cas=0`. It refuses existing paths, including soft-deleted paths, and checks field names afterward without reading values. Use a named Security identity with the creator policy; no values in shell arguments, files, staging or the pipeline. Later value edits use the UI.

**Actions knows where to look from `configuration/application.json`.** It uses subkeys to confirm field names without retrieving values. No staging, pipeline value entry or copying DEV credentials into other environments is required. Terraform's default root contains no secret-value resources; values are never part of the default plan/state. UI edits remain available. An extra/missing field blocks the promotion until reviewed, but a value-only change does not.

[Advanced secret-write alternative](ADVANCED-SECRET-WRITES.md) retains the earlier ephemeral/write-only example for a future requirement to have Terraform write values. It is not the recommended daily route.

The repository is hosted on [GitHub](https://github.com/tekanaid-user/vault-in-vmware/tree/main/13-Vault-Configuration-Promotion). Active workflow files are installed at root `.github/workflows`; this folder retains reference copies. Live jobs require repository variable `VAULT_AUTOMATION_ENABLED=true` after setup. Validation runs without live credentials. Run the [disposable development OIDC pilot](OIDC-PILOT.md) to verify federation on GitHub-hosted runners. See [meeting decisions and Sam’s tracker](MEETING-OUTCOMES.md) and the [pilot runbook](RUNBOOK.md).

## One-time setup : DevOps and Security

| Required setup | Detail |
| --- | --- |
| Terraform and provider | Terraform >=1.11; this example pins Vault provider 5.8.0 and includes generated lock files. Pin a tested Terraform CLI version on runners. |
| Target Vault | Existing KV v2 `secret` mount and `approle` auth; configure real HTTPS addresses/CA. Staging mount is only needed for the optional advanced route. |
| Existing resources | Inventory before applying. Import existing managed policy/AppRole resources into the appropriate state before adopting them. Do not run the demo against an application without owner approval. |
| Remote state | Replace S3 backend placeholders with approved storage; S3 is an example, not a backend decision. Use encryption, versioning and locking, and separate state keys/credentials per environment/root. Backend credentials come from runner identity or on-prem credential delivery, never GitHub secrets or HCL. |
| Git release reference | Put the full reviewed configuration commit SHA in DEV `release.yaml`; Actions requires committed configuration, not a moving branch reference. |
| GitHub OIDC | Configure Vault JWT discovery for `https://token.actions.githubusercontent.com`. Create plan/deploy/drift roles per environment from `bootstrap/github-role.json.example`, with exact repository, main ref, workflow and environment claim bindings. Verify claims against your organization’s tokens. |
| Vault permissions | Plan role reads configuration/structure; deploy role writes only policy/AppRole configuration; drift role reads metadata/subkeys/policy. None needs secret-data read access in the default route. Examples are provided; no superuser/root token is used by CI. |
| Runner | Restricted self-hosted `vault-demo` runner with Vault/backend reachability, CA trust, Python 3.10+ and Terraform. No untrusted PR execution on deployment runners. |
| Actions environments | Create dev/uat/prod, plus dev-plan/uat-plan/prod-plan and dev-drift/uat-drift/prod-drift. Required reviewers on apply environments, especially prod; prevent self-review if available on your organization’s GitHub plan. No environment secrets. |
| Workflow enablement | Workflow files are installed. Configure OIDC bindings to their exact root paths, the self-hosted `vault-demo` runner and GitHub environments; then set repository variable `VAULT_AUTOMATION_ENABLED=true`. No secrets are stored in GitHub. |
| Drift baseline | Review all discovered mounts, adapter permissions, explicit exceptions, metadata field/date format and age threshold. Review `expected_approle` / `expected_kv_config` against live defaults and intentional overrides. Defaults are examples, not the live settings. |

For the regular workflows in this example, bind `workflow_ref`; `job_workflow_ref` is specific to reusable workflow calls. Plan/deploy/drift subjects differ because their GitHub environments differ. For this repository, DEV planning uses `repo:tekanaid-user@37753095/vault-in-vmware@1406319724:environment:dev-plan`; DEV apply ends in `:environment:dev`. The owner/repository IDs are part of its immutable subject. Query the repository OIDC settings before configuring a different repository.

Initial promotion gates use reviewed release PRs plus GitHub deployment approval. The templates do **not** automatically prove a prior environment's successful rollout: reviewers must check that evidence. Automating predecessor-success checks and merge-triggered dispatch is a subsequent enhancement; this pilot deliberately deploys through manual dispatch.

## Security's daily commands

The initial writer supplies each environment's own values directly to Vault; subsequent reads/value edits use the UI. Existing populated locations do not need to be recreated.

| Security action | GitHub Actions handles |
| --- | --- |
| Actions → Vault promotion → choose DEV, UAT or PROD | Reads the pinned release and target settings; authenticates using OIDC; checks keys through subkeys; runs Terraform plan |
| Review plan; approve the protected environment | Fresh OIDC login; verifies saved plan/source/settings; applies that exact plan |
| Advance the next environment's release pointer by PR | Repeats with that environment's own plan and state; no value copying |

**GitHub Actions is the Terraform interface.** Security needs no Terraform shell wrapper or CLI training. `scripts/pipeline.py` is an internal workflow helper; `vault-change.sh` has been removed. DevOps performs one-time imports and backend setup. Destructive plans are rejected; decommissioning remains a separate approved operation.

## Daily drift report

`vault-drift.yml` collects one report per environment using separate read-only OIDC roles, then combines them. It reads KV metadata and **subkeys**, not secret data. It compares against each environment's selected Git schema/policy as well as against other environments.

```bash
# Authenticate separately to each environment for local collection.
./scripts/vault-drift.sh --env dev > dev.json
./scripts/vault-drift.sh --env uat > uat.json
./scripts/vault-drift.sh --env prod > prod.json
./scripts/vault-drift.sh --compare dev.json uat.json prod.json
```

The collector discovers every enabled auth/engine mount, inventories all ACL/password policies, and scans **every KV v2 mount from its metadata root**, including paths outside the demo application. It compares DEV/UAT/PROD inventories and checks the selected application's approved Git baseline. See [exact adapter coverage and exclusions](INVENTORY.md).

| Evidence | Meaning |
| --- | --- |
| Policies, auth, engines | Missing resources and changed allowlisted configuration fields; fingerprints instead of raw content |
| KV paths/keys | Missing/extra/deleted paths and nested key differences through metadata/subkeys; no KV data requests |
| Rotation | Every scanned path: current/overdue/missing/invalid/future date, using the configured metadata field/threshold |
| Incomplete evidence | Denied/failed endpoints remain unknown; missing reports cannot pass parity |
| Approved differences | Exact resource aliases and field exceptions in reviewed settings; environment JWT subjects still checked against Git |
| Review | Adopt intended changes, promote or correct mistakes; report never writes/deletes or declares paths unused |

`python3 scripts/rotation-report.py dev.json uat.json prod.json > rotation-report.json` produces a dedicated age report from existing scan artifacts. Actions saves it alongside `comparison.json`; no additional Vault access. The metadata date is operator maintained, not independent proof of rotation.

Collection exits 0 when a report is produced. Use `--fail-on-findings` for exit 2 on findings, 3 on incomplete evidence (1 on fatal setup failure). The Actions report job saves artifacts first, then fails visibly for findings/incomplete evidence. Reports are in Actions artifacts and the workflow summary; Security owns review. A failed collector cannot silently produce a green comparison.

For cron, run the same collector under a restricted service identity with credentials delivered locally, separately per Vault. Store reports in a protected directory (`umask 077`); schedule collection then `--compare --fail-on-findings`. Never use a root token or put a token on the cron command line. GitHub scheduling uses scoped short-lived OIDC identities instead.

Reports and plan artifacts contain names/configuration and still deserve restricted access. Plan artifacts exclude provider caches, last one day, and contain no application values; review CI logs/artifacts in the DEV pilot before production adoption. Staging cleanup requirements apply only to the optional advanced route.

## Validation and developer keys-only access

See [recorded local results and limits](VALIDATION.md).

Run from repository root:

```bash
python3 -m unittest discover -s 13-Vault-Configuration-Promotion/tests -v
```

Tests launch three isolated loopback Vault dev servers with synthetic values and restricted identities, then stop them and delete temporary logs. They cover differing values with identical structure; missing/extra/nested fields; stale/deleted paths; policy/AppRole/KV differences; rotation dates; incomplete evidence; denied data reads; and create-only writes. A temporary local-state Terraform fixture imports existing policy/AppRole resources, plans/applies, checks idempotence and verifies application values are absent from state. The validation workflow repeats these tests and Terraform syntax/provider validation on hosted or isolated runners without customer access.

Use `bootstrap/developer-keys-policy.hcl` to trial [Read Secret Subkeys](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2#read-secret-subkeys). Example after authenticating with that policy:

```bash
vault read -format=json secret/subkeys/demo/app
```

Leaf values must be `null`. Tests also prove `secret/data/demo/app` returns 403 for the keys-only identity. Vault policies are additive: do not attach a policy granting data read to that developer identity. UI behavior remains unverified; API/CLI support does not imply the UI presents keys-only secrets.

Local validation uses Vault dev mode, not customer DEV/UAT/PROD. Real GitHub OIDC and scoped Terraform plan/apply were verified in the disposable TLS pilot. On-prem connectivity, protected remote state, customer resource imports, actual PROD approvals and customer promotion remain setup/pilot gates. No live secrets or deployments are part of these tests.

References: [Vault subkeys API](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2#read-secret-subkeys) · [Vault write-only guidance](https://registry.terraform.io/providers/hashicorp/vault/5.8.0/docs/guides/using_write_only_attributes) · [GitHub/Vault OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-hashicorp-vault) · [GitHub environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments).

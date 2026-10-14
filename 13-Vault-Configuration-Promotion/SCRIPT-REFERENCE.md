# Workflow and script reference

Use [GETTING-STARTED.md](GETTING-STARTED.md) for the first read-only run and [HANDOFF.md](HANDOFF.md) for responsibilities. This reference explains the execution contracts behind those steps. Examples assume a Git checkout and repository-root working directory. Python requires 3.10+; reporting uses only the standard library.

[local-demo.py](scripts/local-demo.py) provides `start`, `status`, `report`, `stop` for a three-server TLS lab. See [LOCAL-LAB.md](LOCAL-LAB.md). Bootstrap creates only local test configuration; actual CLI collection uses scoped tokens and checks denial/incomplete evidence. Runtime credentials remain outside Git. `drift.py --settings-file` accepts the lab settings without changing live definitions.

## GitHub Actions workflows

All workflow files live at the **repository root** in `.github/workflows`. Their header comments describe triggers, identities, prerequisites, side effects, outputs and relevant controls. Secrets are never workflow form inputs.

| Workflow / operator entry point | Trigger and gate | Execution / identity | Result and effects |
| --- | --- | --- | --- |
| [vault-drift-onboarding.yml](../.github/workflows/vault-drift-onboarding.yml) — Vault drift - getting started | Manual on `main`; choose `environment` and `step`. No automation switch. | `self-hosted, vault-demo`, `ENV-drift`; `claims` requests GitHub JWT only; other steps use `drift_role`. | Claims/authentication/inventory JSON artifact for seven days. No application writes. Collection success means JSON produced; inspect findings/completeness. |
| [vault-drift.yml](../.github/workflows/vault-drift.yml) — Weekly Vault inventory and rotation | Monday 11:00 UTC or manual, `main`; `VAULT_DRIFT_ENABLED=true` **or** legacy `VAULT_AUTOMATION_ENABLED=true`. | Three internal collectors in `ENV-drift`; hosted report job combines artifacts offline. | Per-environment JSON, comparison/rotation JSON and `report.md`, seven days. Final report exits 2 for findings, 3 for incomplete evidence, after saving artifacts. |
| [vault-admin-request.yml](../.github/workflows/vault-admin-request.yml) — Vault admin change request | Manual on `main`; `configure` or `promote`. No automation switch. | Hosted or isolated pilot runner; GitHub contents/PR write permission, no Vault identity. | Validates/edits Git configuration, creates branch/commit/PR. Does not deploy. Bot PR validation/review must be arranged separately. |
| [vault-admin-deploy.yml](../.github/workflows/vault-admin-deploy.yml) — Vault admin deploy | Manual `environment`; plan requires `main` and `VAULT_AUTOMATION_ENABLED=true`; apply depends on plan. | Internal runner; `ENV-plan` / `admin_plan_role`, then `ENV` / `admin_deploy_role`. Reviewers live in GitHub Environment settings. | Imports update state; plan artifact/manifest/summary retained one day; approved saved-plan apply changes configuration. No values/credential issuance; deletes/replacements blocked. |
| [vault-restart-credentials.yml](../.github/workflows/vault-restart-credentials.yml) — Vault restart credential issuance | Manual on `main`, broader switch enabled; `environment` and `expected_version`. | Internal runner; `ENV-credentials` / `credential_role`; requires agreed reviewer protection. | Mints an additional restart SecretID and CAS-writes it into restricted Vault KV. Emits only delivery version; old credentials stay valid. |
| [vault-oidc-pilot.yml](../.github/workflows/vault-oidc-pilot.yml) — Vault development OIDC pilot | Manual on `main`, hosted/isolated choice; independent of live switches. | `vault-pilot` Environment, GitHub JWT; disposable synthetic TLS Vaults on one runner. | Checks scoped access, trust rejection, Terraform and introduced drift. Safe pilot report retained seven days. Fixed demonstration identity must be adapted deliberately for another repo. |
| [vault-validate.yml](../.github/workflows/vault-validate.yml) — Validate Vault promotion and drift | Section 13/workflow PRs, main pushes, or manual. | Hosted runner or manual isolated pilot; contents read only, no OIDC permission. | Synthetic regression tests, backend-disabled Terraform validation, Bash syntax and CLI help. Does not establish live acceptance. |

`vault-demo` is the existing example label, not an instruction to use an application server. Change it in the relevant workflows to your approved internal runner label. `vault-pilot` is for disposable test jobs. Keep untrusted PR validation away from deployment runners. GitHub Enterprise Server may require compatible action versions and replacement of hosted jobs.

Workflow dependencies such as action SHAs, tool versions and runner image/checksum are pinned. When upgrading, review the corresponding source/checksum and rerun validation; comments do not authorize an upgrade.

## Reporting scripts: first-run and weekly paths

| Script | Inputs / dependency | Output / exit / behavior |
| --- | --- | --- |
| [oidc-check.py](scripts/oidc-check.py) | `--env`; optional `--claims-only`. Settings audience, Actions token-request variables and `id-token: write`. | Selected diagnostic claims without Vault access, or login + mount-count JSON. Authentication explicitly rejects local-token fallback. Owned Vault token revoked; no full-coverage claim. Runtime 0/1. |
| [drift.py](scripts/drift.py) | `--env ENV --inventory-only`, or `--compare [REPORTS...]`. Collection uses settings and drift identity; comparison is offline. | JSON to stdout. Inventory-only bypasses original demo release/app checks, **not** configured inventory expectations. Unknown reads remain incomplete. Normal collection exits 0 when JSON exists; `--fail-on-findings` adds 2/3 result codes. Runtime/format failure 1. |
| [inventory.py](scripts/inventory.py) | Imported library; `scan(cfg, call, normalization_helpers..., today)` and `compare(inventories)`. | Category maps, sanitized configuration fingerprints, paths/field names, findings and coverage. No login/CLI of its own. Exclusions and aliases/exceptions are explicit. See [coverage](INVENTORY.md). |
| [rotation-report.py](scripts/rotation-report.py) | One or more positional collector/comparison JSON files. No identity or connection. | Counts plus sorted environment/path/status/age rows. Missing environments keep incomplete status. Runtime 0 produces report, 1 invalid input. No raw custom metadata or last-access inference. |
| [render-report.py](scripts/render-report.py) | Comparison JSON and rotation JSON, positional. Offline. | Markdown tables to stdout; escapes table cells and selects only report fields. Runtime 0 renders, 1 invalid input. Does not decide workflow success. |
| [vault-drift.sh](scripts/vault-drift.sh) | Bash wrapper; forwards all arguments to adjacent `drift.py`. | Same stdout/stderr, signals and exit status as Python because it uses `exec`. Active workflows invoke Python directly. |

Typical command shapes:

For the UI download location and an actual claims artifact with field-to-role mapping, see [Observed DEV claims](examples/DEV-CLAIMS-REFERENCE.md). Claims retrieval is separate from Vault login and collection.

```bash
# In an Actions job: inspection, scoped login, then one environment's inventory.
python3 13-Vault-Configuration-Promotion/scripts/oidc-check.py --env dev --claims-only
python3 13-Vault-Configuration-Promotion/scripts/oidc-check.py --env dev
python3 13-Vault-Configuration-Promotion/scripts/drift.py --env dev --inventory-only > dev.json

# Offline: compare downloaded collector artifacts, then extract/render.
python3 13-Vault-Configuration-Promotion/scripts/drift.py \
  --compare dev.json uat.json prod.json > comparison.json
python3 13-Vault-Configuration-Promotion/scripts/rotation-report.py comparison.json > rotation-report.json
python3 13-Vault-Configuration-Promotion/scripts/render-report.py comparison.json rotation-report.json > report.md
```

These are invocation examples, not setup substitutes. A local inventory run can reuse an approved drift-scoped login, but it does not prove GitHub federation. The OIDC authentication check requires Actions.

### Interpreting failures

`--fail-on-findings` is optional in the Python CLI. The weekly workflow instead uploads artifacts, renders the report, and applies its own final exit check. Incomplete evidence takes precedence over ordinary differences. The onboarding workflow does not apply that final classification, so review its JSON even when the job is green.

Like other Python CLIs, malformed arguments cause argparse to exit 2; this is a usage error rather than an evaluated finding. Operational failure is distinct from a successfully produced JSON document whose `complete` is false. Safe HTTP errors retain only status and path; response bodies are suppressed. Tokens are never troubleshooting output.

## Shared configuration and identity contract

[common.py](scripts/common.py) is imported, not run directly. Its top-level initialization discovers the Git root; keep the checkout and Section 13 path intact. It provides:

- `settings(env, live=True)`: reads `environments/<env>/settings.json`. The JSON `vault_addr` selects the endpoint; a shell `VAULT_ADDR` does not override it. HTTPS/non-placeholder live URLs and absence of namespaces are enforced.
- `api(...)`: 30-second JSON requests with URL-escaped paths and optional query parameters. `VAULT_CACERT` supplies runner → Vault trust; default system trust applies when absent. It supports reads **and writes**; the caller/policy determines scope.
- `github_jwt(audience)` and `authenticate(cfg, role_kind)`: request a GitHub identity and exchange it through `auth/<jwt_auth_path>/login`. Role kinds map to `<kind>_role` settings. Outside Actions, reusable helpers fall back to `VAULT_TOKEN`, then `~/.vault-token`.
- `close_token(cfg, token, owned)`: best-effort revoke-self only for newly owned identities. Operator-supplied tokens remain untouched; short TTL covers failed revocation. Renewal is not implemented.
- `revision`, `read_revision`, `app_definition`: original selected-application baseline helpers. They use `release.yaml` and configuration at a full SHA. Scheduled inventory-only reporting avoids that baseline.

GitHub's issuer trust is configured in Vault, while the audience/JWT mount/role names are in settings. Vault-server → issuer CA/discovery connectivity and runner → Vault CA/connectivity are separate concerns. Values-free reports still reveal paths and infrastructure structure; restrict readers accordingly. Fingerprinting is an equality tool, **not** encryption or a substitute for excluding sensitive fields.

## Workstream 1 scripts: configuration and credentials

Security normally launches the workflows. These are implementation helpers; running them manually can change Git files, state, Vault configuration or credentials.

| Script | Invocation / inputs | Side effects and safeguards |
| --- | --- | --- |
| [admin-request.py](scripts/admin-request.py) | `--operation configure|promote --environment ENV --setup-mode applications|restart|both --applications "..." --ticket "..."`; optional keys/settings, promote SHA. | `generate()` returns path/content; `main()` writes one catalog/release file. Requires approved name/field patterns, supported non-secret settings, valid types/CIDRs and SHA ancestry. Workflow, not Python, commits/pushes/creates the PR. |
| [admin-pipeline.py](scripts/admin-pipeline.py) | `plan --env ENV` or `apply --env ENV --digest DIGEST`. Needs Terraform, reviewed `admin-release.json`, Git history, backend and admin role settings. | Plan copies pinned source/lockfile into `.admin-run`, initializes/imports state, writes `approved.tfplan`, `summary.json`, `manifest.json` and emits `manifest_digest` to `GITHUB_OUTPUT`. Apply verifies artifact hashes and target/settings/backend against approval, then applies that exact plan with fresh identity. Workflow cleans local `.admin-run`; script closes owned token. |
| [restart-credentials.py](scripts/restart-credentials.py) | `--env ENV --expected-version N`; existing AppRole, KV v2 delivery mount/path, credential identity. | Version check before minting plus CAS write prevents overwriting an unexpected delivery version. Failed delivery attempts accessor destruction for the new credential; a cleanup failure needs manual audit investigation. Earlier credentials are retained. No credential artifacts/state/stdout. |

`expected_version=0` means no delivery version yet, not permission to overwrite an existing entry. Do not resolve a version conflict by guessing a number. Review the actual delivery metadata through approved access.

Deployment imports can write remote state even before an apply. Use a protected backend and explicit environment state; reporting needs neither. Environment reviewers are configured outside the YAML. DEV → UAT → PROD predecessor success is checked by reviewers, not automatically enforced by the pipeline. See [RUNBOOK.md](RUNBOOK.md).

## Demonstration and runner helpers

| File | Usage / boundary |
| --- | --- |
| [oidc-pilot.py](scripts/oidc-pilot.py) | Actions mode exercises actual federation for the fixed demonstration repository. `--local --output /tmp/pilot-report.json` exercises mechanics only with locally scoped tokens. Starts three disposable loopback TLS Vault dev servers and Terraform local state; synthetic values are checked absent from report/state. Finally stops servers, removes temporary files and restores caller environment. Requires Vault/Terraform/Git/Python. |
| [pilot-runner/start.py](pilot-runner/start.py) | After building the image in [OIDC-PILOT.md](OIDC-PILOT.md), run from repo root with Docker and the documented `gh` account login. Registers one runner/container, writes a mode-0600 temporary registration env file and removes it after launch. Prints container identity only. Fixed account/repo/image references are intentional demo bindings. |
| [pilot-runner/entrypoint.sh](pilot-runner/entrypoint.sh) | Runs **inside** the container. Requires `RUNNER_NAME`/`RUNNER_REGISTRATION_TOKEN`; registers against the demo repo with `vault-pilot`, ephemeral/single-job behavior and disabled auto-update, unsets token, then `exec`s the runner. Rebuild image for upgrades. |
| [pilot-runner/Dockerfile](pilot-runner/Dockerfile) | Packages a checksum-pinned runner under an unprivileged user. `start.py` supplies CPU/memory limits, `--rm`, and no host mounts/Docker socket. Docker administrators can inspect registration-time environment; use trusted hosts. Interrupted registration may require offline-runner cleanup. |

## Regression-only files

Run `python3 -m unittest discover -s 13-Vault-Configuration-Promotion/tests -v` from repo root. Test module docstrings explain their scope. The suite covers reporting/unknown evidence, adapters/permissions, form validation, import/apply/idempotence, artifact integrity, credential cleanup and onboarding/report rendering.

`tests/fixtures/create-secret.py` is historical create-only regression code. It uses CAS=0 and hidden prompts, and can write a synthetic secret; it is **not an active onboarding or Security entry point**. Active configuration workflows do not accept application values. Tests start disposable local Vaults, may use temporary Terraform local state, and clean fixture processes/files. Passing them does not establish production acceptance or a successful GitHub Actions run.

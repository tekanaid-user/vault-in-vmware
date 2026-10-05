# Development OIDC pilot

Run **Actions → Vault development OIDC pilot → Run workflow (main)**. Select `hosted`, or select `isolated` after starting a disposable container runner below.

This creates three disposable Vault dev servers on one Ubuntu runner (GitHub-hosted or an isolated ephemeral container). Each listens only on loopback with generated TLS certificates, keeps data in memory and is destroyed at the end. DEV/UAT/PROD names represent simulated environments. No public endpoint, application credentials or Vault tokens are put in GitHub secrets.

| Stage | What is exercised |
| --- | --- |
| Bootstrap | Generate synthetic values in memory; configure policies/AppRole and JWT auth on each Vault. The temporary root token is used only for setup and controlled test changes, never for collection or Terraform. |
| OIDC | GitHub issues a signed JWT using `id-token: write`. Vault validates issuer/signature/audience and exact repository, main ref, workflow, event and `vault-pilot` environment subject. The subject includes this repository’s immutable owner/repository IDs. No GitHub OIDC server needs to be installed. |
| Negative access | Reject an intentionally mismatched repository binding. Reporting identity can read subkeys but receives 403 for data reads. |
| Terraform Community CLI | Use distinct plan/deploy policies with OIDC tokens. Import the example resources into disposable local state, create a saved plan, apply with a fresh identity, then check no remaining changes. Application values are absent from state. |
| Workstream 2 | Compare three matching baselines despite different synthetic values. Introduce a UAT field difference and overdue rotation date; confirm both are detected. |
| Cleanup | Revoke owned tokens, stop Vault processes, delete TLS keys, state, plans and server logs. Upload only the values-free report. |

The job is manually dispatched from main and uses the `vault-pilot` GitHub environment. It does not depend on `VAULT_AUTOMATION_ENABLED`; that flag controls workflows for externally hosted Vaults.

## Repository configuration prepared

| Setting | Configuration |
| --- | --- |
| Runner for pilot/validation | Select hosted `ubuntu-latest` or a disposable `self-hosted, vault-pilot` container; pinned official Vault/Terraform downloads verified with release checksums. |
| Environments | `vault-pilot`, `dev`, `uat`, `prod`, plus plan/drift environments for each target; all restricted to main. |
| Apply review | UAT and PROD require review from the configured collaborator; self-review prevented. |
| Live workflow switch | `VAULT_AUTOMATION_ENABLED=false` until real addresses, scoped OIDC roles, remote state/imports and a reachable runner are ready. |
| Credentials | No environment secrets or stored Vault tokens configured. |

## Isolated runner option

From repository root, with Docker and the repository owner's existing local `gh` login:

```bash
docker build -t vault-oidc-pilot-runner:2.337.0 13-Vault-Configuration-Promotion/pilot-runner
python3 13-Vault-Configuration-Promotion/pilot-runner/start.py
```

Then dispatch the pilot or validation workflow with `runner=isolated`. One container accepts one job, unregisters and is removed afterward. The registration token is generated through the GitHub API, kept in a temporary protected file for startup and deleted immediately; it is not stored in GitHub secrets or Git. The container runs as a non-root user with CPU/memory limits, no host mounts and no Docker socket. It uses its own filesystem/network namespace. Start one container per job; `docker stop <printed-name>` stops an unused container. Check/remove an offline registration if a runner is interrupted before completing its job.

This label is for the disposable pilot only. The actual on-prem deployment workflows use `vault-demo` and need separately configured network access.

## Local reproduction

```bash
python3 13-Vault-Configuration-Promotion/scripts/oidc-pilot.py --local --output /tmp/pilot-report.json
```

Run from repository root with Vault and Terraform installed. Local mode checks TLS, scoped tokens, Terraform and reporting; it **does not test GitHub OIDC**. Only a successful hosted pilot establishes federation evidence.

## External deployment remains separate

For real DEV/UAT/PROD, provision a restricted self-hosted runner in a network that reaches those Vaults and state storage, configure actual HTTPS addresses and trust the real workflow/environment claims in each Vault. Do not point a customer environment at a transient localhost address or treat disposable local state as a remote production backend. Follow [runbook](RUNBOOK.md).

# DEV GitHub identity: observed reference

[github-dev-claims.json](github-dev-claims.json) preserves the selected claims from the demonstration repository's successful **DEV / claims** step. This is actual GitHub-issued identity metadata, not a synthetic drift report. It contains no JWT, bearer token, Vault token or application secret value.

**Source:** [Vault drift - getting started, run 38469756292](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/38469756292), artifact `vault-onboarding-dev-claims`; JSON supplied from the downloaded artifact. The workflow ran at commit `47ab1608ee55c2556c8dcb5e6adaacdaf44fa2d9` in GitHub Environment `dev-drift`.

## Find this output in GitHub's UI

1. Actions → **Vault drift - getting started** → choose the completed run → **Summary**.
2. If a rerun is queued/running, wait for completion and refresh the page.
3. In **Artifacts**, download **vault-onboarding-dev-claims**.
4. Extract the ZIP and open **dev-claims.json** in a text editor.

The Summary confirms completion; the JSON is in the downloadable artifact, not an inline preview. The filename inside the artifact differs from this reference filename so the repository example is clearly identified.

## Map claims to the Vault setup

| Observed claim | Used for |
| --- | --- |
| `iss` = `https://token.actions.githubusercontent.com` | Vault JWT auth backend `bound_issuer`; this public GitHub setup uses the same URL for `oidc_discovery_url`. |
| `aud` = `vault-demo` | Role `bound_audiences`, matching `settings.json` `oidc_audience`. |
| `sub` = `repo:tekanaid-user@37753095/vault-in-vmware@1406319724:environment:dev-drift` | Exact DEV `bound_claims.sub`. This observed immutable-ID subject includes the GitHub Environment; do not substitute a branch-only subject. |
| `repository`, `repository_id`, `repository_owner_id` | Exact repository/owner bindings in the drift-role template. These IDs are for the demonstration repository only. |
| `ref` = `refs/heads/main` | Exact permitted branch binding. |
| `workflow_ref` | Exact onboarding workflow binding. The drift-role template also permits the weekly workflow's exact ref so the scoped role can serve both workflows. |
| `event_name` = `workflow_dispatch` | This run was manually launched. The template additionally permits `schedule` for the weekly report. |

**Use this JSON as a reference, not as a universal policy.** Another repository, owner, environment, issuer customization or subject customization requires its own claims run and reviewed bindings. Repeat claims inspection for UAT/PROD; do not assume this DEV subject authorizes them. The two workflow refs and event names in the template are deliberate allowed values; only the onboarding/manual values were observed in this artifact.

## What succeeded, and what comes next

This confirms runner execution and retrieval of a GitHub OIDC token's selected claims. Decoding these claims does not verify the signature, and the step did not contact Vault. It does **not** establish Vault authentication, read permissions or a drift scan.

Continue with [GETTING-STARTED.md, step 5](../GETTING-STARTED.md#5-enable-jwtoidc-trust-in-dev-vault): install reviewed JWT issuer trust, the drift policy and DEV role; set the real DEV HTTPS endpoint/CA in the documented settings/trust locations. Then run `dev / authenticate`, followed by `dev / collect`. A placeholder `vault_addr` still prevents those live steps even though claims inspection succeeds.

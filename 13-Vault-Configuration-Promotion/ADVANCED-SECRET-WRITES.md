# Optional alternative: Terraform writes the values

The recommended workflow is direct Vault UI writes plus Terraform policy/configuration promotion. This alternative is only relevant if OPERS later requires Terraform to perform secret writes. It adds staging and requires additional permissions; do not enable it for the default workflow.

## How different values reach each environment

1. Security logs into the selected Vault using their existing local authentication.
2. `stage-secret.sh` asks for `username` and `password` with hidden terminal prompts, then writes them to that environment's restricted `promotion-inputs` KV v2 mount. It prints only a request ID.
3. An approved Actions job obtains a short-lived Vault token by exchanging GitHub's OIDC JWT. It receives only the request ID.
4. Terraform reads staging version **1** through `ephemeral "vault_kv_secret_v2"` and passes `data_json` directly into the destination's `data_json_wo`. Values are omitted from Terraform plan/state.
5. The wrapper verifies the destination version/field names and permanently deletes the staged path after success. Failed writes retain staging for investigation; its 24-hour soft-delete expiry is a fallback, not permanent cleanup.

Each environment receives its **own** payload; the Git schema/policy revision is shared. Staging records bind the payload to environment, configuration SHA, destination version and write-version. CAS rejects writes when a UI edit changed the destination since staging. A policy-only apply never executes the secret-write root.

This pilot uses one application with flat string fields. Nested structures, multiple applications, duplicate workflow dispatches and stale staged-input cleanup need deliberate extensions. Ordinary secret data sources and `data_json` resource arguments are not used. Ephemeral does not mean “never in memory”: the runner sees values during the operation, so restrict runner access and disable debug logging.

## Advanced commands

```bash
./scripts/stage-secret.sh --env dev --write-version 1
./scripts/vault-change.sh plan --env dev --operation secret-write --request-id <printed-id>
./scripts/vault-change.sh apply --env dev --run <saved-run-path> --approve-environment dev
```

Requires a restricted KV v2 `promotion-inputs` mount, a Security staging identity, and dedicated plan/deploy roles granting the extra staged-input/target-write capabilities. Add those capabilities only for this route. The existing secret-write Terraform root and staging wrapper are retained as an example; regular policy promotion does not call them. Supply a fresh per-environment payload and increasing write-version for every intentional write. Maintain cleanup for expired/failed requests; soft deletion does not permanently remove data.

# Vault metrics with DogStatsD

Configure each Vault server to send telemetry to the Datadog Agent running on the same VM. The Agent receives it through its local DogStatsD listener at `127.0.0.1:8125` and sends metrics to Datadog.

## What to do today

1. Select one development Vault VM. If the Datadog Agent is absent, install it using the Linux installation command generated in the organization's Datadog account. The installer needs that organization's API key and Datadog site. Obtain the key through the approved secrets process; do not put it in this repository.
2. On the VM, merge the [Agent example](datadog-agent.yaml.example) into `/etc/datadog-agent/datadog.yaml`. Set the correct site, API key, environment, and cluster. Keep any existing Agent settings needed by that VM. The Agent's DogStatsD listener must be enabled on local UDP port 8125.
3. Start or restart the Agent and verify it is healthy:

   ```bash
   sudo systemctl enable --now datadog-agent
   sudo systemctl restart datadog-agent
   sudo datadog-agent status
   sudo ss -lunp '( sport = :8125 )'
   ```

4. Add the [Vault `telemetry` example](vault-telemetry-dogstatsd.hcl.example) to the VM's **existing Vault configuration**. Replace both `CHANGE_ME` values with the correct environment and cluster names. Validate the configuration with the installed Vault version, then apply it through the normal change procedure. Check whether that deployment requires a Vault restart.
5. In Datadog, confirm Vault metrics arrive from that VM and carry the expected host, `env`, `service`, and `cluster` tags. Also confirm the Agent reports a valid API key and successful metric submission.
6. After the development check succeeds, repeat on the remaining Vault VMs. Confirm metrics arrive from **each** VM, then assign dashboard and alert ownership.

Both examples are configuration fragments to merge into existing files. Keep the DogStatsD listener local to the VM. Do not commit a real API key.

## References

- [Vault DogStatsD telemetry settings](https://developer.hashicorp.com/vault/docs/configuration/telemetry#dogstatsd)
- [Datadog DogStatsD host Agent setup](https://docs.datadoghq.com/extend/dogstatsd/?tab=hostagent)
- [Datadog Agent installation](https://docs.datadoghq.com/getting_started/agent/)
- [Datadog Agent commands](https://docs.datadoghq.com/agent/configuration/agent-commands/)

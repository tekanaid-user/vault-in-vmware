#!/usr/bin/env bash
set -euo pipefail
cd /opt/actions-runner
./config.sh --unattended --url https://github.com/tekanaid-user/vault-in-vmware \
  --token "$RUNNER_REGISTRATION_TOKEN" --name "$RUNNER_NAME" \
  --labels vault-pilot --ephemeral --disableupdate --work _work
unset RUNNER_REGISTRATION_TOKEN
exec ./run.sh

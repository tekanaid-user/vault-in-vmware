#!/usr/bin/env python3
"""Start one disposable Docker runner for the demonstration repository.

Run from repo root after building vault-oidc-pilot-runner:2.337.0. Requires Docker
and the existing gh login for tekanaid-user with runner-registration permission.
Requests a short-lived registration token, writes a mode-0600 temporary env file,
starts a resource-limited --rm container with no host mounts/Docker socket, then
removes the file. Container environment contains the registration token during
setup; trusted Docker administrators can inspect it. The entrypoint unsets it
before running a single ephemeral job. Prints only container name/instructions.
No automatic cleanup of a runner interrupted before registration completes;
inspect/remove offline registrations as needed. See OIDC-PILOT.md."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid


def main():
    # Use the repository owner's existing local gh credentials; never print them.
    """Register/start one ephemeral demonstration container using existing gh credentials."""
    env = os.environ.copy()
    env['GH_TOKEN'] = subprocess.check_output(['gh', 'auth', 'token', '--user', 'tekanaid-user'], text=True).strip()
    token = json.loads(subprocess.check_output(['gh', 'api', '--method', 'POST', 'repos/tekanaid-user/vault-in-vmware/actions/runners/registration-token'], env=env))['token']
    name = 'vault-pilot-' + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix='vault-runner-registration-') as temporary:
        path = Path(temporary) / 'registration.env'
        path.write_text(f'RUNNER_REGISTRATION_TOKEN={token}\nRUNNER_NAME={name}\n')
        path.chmod(0o600)
        container = subprocess.check_output(['docker', 'run', '--detach', '--rm', '--name', name, '--cpus=2', '--memory=4g', '--env-file', str(path), 'vault-oidc-pilot-runner:2.337.0'], text=True).strip()
    print(f'Started ephemeral runner/container {name}; inspect with docker logs {name}.')
    print('It unregisters after one job. No host mounts or cloud credentials are attached.')


if __name__ == '__main__':
    main()

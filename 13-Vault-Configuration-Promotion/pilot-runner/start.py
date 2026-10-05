#!/usr/bin/env python3
"""Register one disposable, container-isolated pilot runner using existing gh login."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid


def main():
    # Use the repository owner's existing local gh credentials; never print them.
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

#!/usr/bin/env python3
"""Run a repeatable three-environment TLS Vault lab and collect actual API evidence.

Commands: start, report, status, stop. Vault CLI, Git and Python 3.10+ required.
Servers are localhost-only Vault dev-mode processes with in-memory test data;
they remain running until stop/process exit/reboot. DEV/UAT/PROD are lab labels.
Private tokens, certificates and logs live outside Git in a mode-0700 state dir.
Only start seeds deliberately different test configuration. report uses fresh
read-only tokens, production collectors, real 403 checks and offline rendering.
No application values or tokens are exported. This is not production deployment.
See LOCAL-LAB.md for commands, lifecycle and evidence boundaries.
"""
import argparse
from contextlib import contextmanager
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import uuid

from common import BASE, ApiError, api, settings
import drift

PORTS = {'dev': 18520, 'uat': 18530, 'prod': 18540}
DEFAULT_STATE = Path.home() / '.local/state/vault-drift-demo'
CHILDREN = {}  # Retain/reap children when start/stop run in the same test process.


def private_json(path, data):
    """Write lab credentials with restrictive permissions before opening the file."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(data, output, indent=2)
        output.write('\n')


@contextmanager
def local_identity(ca, token=None):
    """Scope TLS/token overrides to one operation; restore the caller's environment."""
    saved = {key: os.environ.get(key) for key in ('VAULT_CACERT', 'VAULT_TOKEN', 'GITHUB_ACTIONS')}
    os.environ['VAULT_CACERT'] = str(ca)
    os.environ['GITHUB_ACTIONS'] = 'false'
    if token:
        os.environ['VAULT_TOKEN'] = token
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def call(item, token, method, path, payload=None):
    """Call only this lab endpoint with its generated CA, suppressing response errors."""
    with local_identity(item['ca']):
        return api(item['settings'], token, method, path, payload)


def seed(item, env, sensitive):
    """Create controlled policy/config/path/field/rotation differences on a new Vault."""
    root = item['root_token']
    def write(path, data):
        return call(item, root, 'POST', path, data)
    policy = (BASE / 'bootstrap/drift-policy.hcl').read_text() + '''
path "nested/secrets/metadata" { capabilities = ["list"] }
path "nested/secrets/metadata/*" { capabilities = ["read", "list"] }
path "nested/secrets/subkeys/*" { capabilities = ["read"] }
path "nested/secrets/config" { capabilities = ["read"] }
path "sys/mounts/nested/secrets/tune" { capabilities = ["read"] }
'''
    write('sys/policies/acl/github-drift', {'policy': policy})
    write('sys/policies/acl/lab-denied', {'policy': 'path "*" { capabilities = ["deny"] }'})
    read_policy = 'path "secret/data/example-app/*" { capabilities = ["read"] }'
    if env == 'uat':
        read_policy = read_policy.replace('["read"]', '["read", "update"]')
    write('sys/policies/acl/application-reader', {'policy': read_policy})
    if env == 'dev':
        write('sys/policies/acl/dev-only', {'policy': 'path "secret/subkeys/prototype/*" { capabilities = ["read"] }'})
    length = 24 if env == 'prod' else 20
    write('sys/policies/password/application', {'policy': f'length = {length}\nrule "charset" {{ charset = "abcdefghijk123456789" }}'})
    for mount in ('apps', 'nested/secrets'):
        write('sys/mounts/' + mount, {'type': 'kv', 'options': {'version': '2'}})
    write('secret/config', {'max_versions': 5 if env == 'uat' else 10})
    write('sys/mounts/secret/tune', {'default_lease_ttl': '2h' if env == 'prod' else '1h'})
    write('sys/auth/approle', {'type': 'approle'})
    write('auth/approle/role/example-app', {'token_policies': ['application-reader'], 'token_ttl': 7200 if env == 'uat' else 3600})
    write('sys/auth/company-ldap', {'type': 'ldap'})
    write('auth/company-ldap/config', {'url': 'ldap://directory.example.invalid', 'userdn': 'ou=users', 'groupdn': 'ou=groups', 'userattr': 'uid'})
    write('auth/company-ldap/groups/developers', {'policies': ['application-reader'] if env != 'prod' else ['default']})
    write('auth/company-ldap/users/demo-user', {'groups': ['developers']})
    write('sys/auth/cluster', {'type': 'kubernetes'})
    write('auth/cluster/config', {'kubernetes_host': 'https://127.0.0.1:6443', 'disable_local_ca_jwt': True})
    write('auth/cluster/role/example-app', {'bound_service_account_names': ['example-app'], 'bound_service_account_namespaces': ['lab'], 'token_policies': ['application-reader']})
    if env == 'dev':
        write('sys/auth/local-users', {'type': 'userpass'})
        password = uuid.uuid4().hex
        sensitive.append(password)
        write('auth/local-users/users/demo-user', {'password': password, 'token_policies': ['application-reader']})
        write('sys/mounts/prototype', {'type': 'kv', 'options': {'version': '2'}})
    write('sys/mounts/encryption', {'type': 'transit'})
    write('encryption/keys/application', {'type': 'aes256-gcm96'})
    if env == 'prod':
        write('encryption/keys/production-only', {'type': 'aes256-gcm96'})
    write('sys/mounts/certificates', {'type': 'pki'})
    write('certificates/roles/application', {'allowed_domains': ['example.invalid'], 'allow_subdomains': env != 'prod'})
    # Configure real GitHub issuer trust, but local collection uses scoped tokens.
    write('sys/auth/github', {'type': 'jwt'})
    write('auth/github/config', {'oidc_discovery_url': 'https://token.actions.githubusercontent.com', 'bound_issuer': 'https://token.actions.githubusercontent.com'})
    template = json.loads((BASE / 'bootstrap/github-drift-role.json.example').read_text())
    repo = 'tekanaid-user/vault-in-vmware'
    template['bound_claims'].update(repository=repo, repository_id='1406319724', repository_owner_id='37753095',
        sub=f'repo:tekanaid-user@37753095/vault-in-vmware@1406319724:environment:{env}-drift',
        workflow_ref=[f'{repo}/.github/workflows/{name}@refs/heads/main' for name in ('vault-drift-onboarding.yml', 'vault-drift.yml')])
    write('auth/github/role/github-drift', template)
    today = dt.datetime.now(dt.timezone.utc).date()
    current = (today - dt.timedelta(days=10)).isoformat()
    def secret(mount, path, fields, date=current):
        value = uuid.uuid4().hex
        sensitive.append(value)
        def payload(shape):
            return {key: payload(child) if isinstance(child, dict) else value for key, child in shape.items()}
        write(f'{mount}/data/{path}', {'options': {'cas': 0}, 'data': payload(fields)})
        if date is not None:
            write(f'{mount}/metadata/{path}', {'custom_metadata': {'password_cycle_date': date}})
    secret('secret', 'example-app/config', {'username': None} if env == 'uat' else {'username': None, 'password': None},
           (today - dt.timedelta(days=120)).isoformat() if env == 'uat' else current)
    secret('apps', 'service/config', {'connection': {'host': None, 'port': None, **({'region': None} if env == 'prod' else {})}})
    secret('nested/secrets', 'service/config', {'api_key': None})
    secret('secret', 'retired/config', {'password': None})
    if env == 'prod':
        call(item, root, 'DELETE', 'secret/data/retired/config')
    if env == 'dev':
        secret('secret', 'example-app-old/config', {'username': None, 'password': None}, None)
        secret('secret', 'invalid-date/config', {'password': None}, 'not-a-date')
    if env == 'prod':
        secret('secret', 'future-date/config', {'password': None}, (today + dt.timedelta(days=10)).isoformat())


def owned_process(item):
    """Verify Linux process identity before signalling a recorded PID (avoid PID reuse)."""
    try:
        args = Path(f"/proc/{item['pid']}/cmdline").read_bytes().split(b'\0')
        return f"-dev-tls-cert-dir={item['directory']}".encode() in args
    except FileNotFoundError:
        return False


def stop(state):
    """Stop only tracked matching lab processes; retain protected files for inspection."""
    metadata = state / 'state.json'
    if not metadata.exists():
        return
    document = json.loads(metadata.read_text())
    for item in document['environments'].values():
        if owned_process(item):
            os.kill(item['pid'], signal.SIGTERM)
    for _ in range(100):
        if not any(owned_process(item) for item in document['environments'].values()):
            break
        time.sleep(.1)
    if any(owned_process(item) for item in document['environments'].values()):
        raise RuntimeError('Lab process did not stop; state retained')
    for item in document['environments'].values():
        process = CHILDREN.pop(item['pid'], None)
        if process:
            process.wait(timeout=10)
    metadata.unlink()


def start(state, ports=None):
    """Start three localhost TLS Vaults once; refuse stale state or occupied ports."""
    metadata = state / 'state.json'
    ports = ports or PORTS
    if metadata.exists():
        existing = json.loads(metadata.read_text())
        if all(owned_process(item) for item in existing['environments'].values()):
            print('Lab already running; use report to collect it again.')
            return
        raise RuntimeError('Stale/partial lab state: run stop before starting again')
    for port in ports.values():
        for candidate in (port, port + 1):
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', candidate))
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if state.stat().st_mode & 0o077:
        raise ValueError('State directory must be private (mode 0700)')
    sensitive = []
    document = {'schema_version': 1, 'environments': {}, 'sensitive_test_values': sensitive}
    try:
        for env, port in ports.items():
            directory = state / env
            directory.mkdir(exist_ok=True, mode=0o700)
            root = uuid.uuid4().hex
            sensitive.append(root)
            cfg = settings(env, live=False)
            cfg.update(vault_addr=f'https://127.0.0.1:{port}', drift_role='github-drift',
                       inventory_expected_fields={}, inventory_resource_aliases={}, inventory_comparison_exceptions=[])
            item = {'directory': str(directory), 'ca': str(directory / 'vault-ca.pem'), 'settings': cfg, 'root_token': root}
            private_json(directory / 'settings.json', cfg)
            child_env = {key: value for key, value in os.environ.items() if not key.startswith('VAULT_')}
            child_env['VAULT_DEV_ROOT_TOKEN_ID'] = root
            fd = os.open(directory / 'server.log', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as log:
                process = subprocess.Popen(['vault', 'server', '-dev', '-dev-tls', '-dev-no-store-token',
                    f'-dev-tls-cert-dir={directory}', f'-dev-listen-address=127.0.0.1:{port}'],
                    env=child_env, stdout=log, stderr=log, start_new_session=True)
            item['pid'] = process.pid
            CHILDREN[process.pid] = process
            document['environments'][env] = item
            private_json(metadata, document)
            for _ in range(150):
                try:
                    call(item, root, 'GET', 'sys/health')
                    break
                except Exception:
                    if process.poll() is not None:
                        raise RuntimeError('Vault exited during startup; inspect protected server log')
                    time.sleep(.1)
            else:
                raise RuntimeError('Vault startup timed out')
            seed(item, env, sensitive)
            private_json(metadata, document)
        print('Started three real TLS Vault dev-mode servers on localhost: ' + ', '.join(f'{e}={p}' for e, p in ports.items()))
    except Exception:
        stop(state)
        raise


def module(name, filename):
    """Load a reporting helper without changing the public script filenames."""
    spec = importlib.util.spec_from_file_location(name, BASE / 'scripts' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def report(state, output):
    """Collect real APIs with fresh scoped identities, verify differences/denials and export."""
    document = json.loads((state / 'state.json').read_text())
    reports, checks, forbidden = [], [], list(document['sensitive_test_values'])
    for env, item in document['environments'].items():
        if not owned_process(item):
            raise RuntimeError('Lab process is no longer running')
        token = call(item, item['root_token'], 'POST', 'auth/token/create',
                     {'policies': ['github-drift'], 'no_default_policy': True, 'ttl': '15m'})['auth']['client_token']
        forbidden.append(token)
        try:
            with local_identity(item['ca'], token):
                # Exercise the actual CLI, not a preassembled inventory or test double.
                private_json(Path(item['directory']) / 'settings.json', item['settings'])
                result = subprocess.run([sys.executable, str(BASE / 'scripts/drift.py'), '--env', env,
                    '--inventory-only', '--settings-file', str(Path(item['directory']) / 'settings.json')],
                    capture_output=True, text=True, check=True)
                snapshot = json.loads(result.stdout)
            if not snapshot['complete']:
                raise RuntimeError('Supported inventory incomplete; inspect protected lab setup')
            for mount, path in [('secret', 'example-app/config'), ('apps', 'service/config'), ('nested/secrets', 'service/config')]:
                fields = call(item, token, 'GET', f'{mount}/subkeys/{path}')['data']['subkeys']
                drift.leaf_fields(fields)  # Reject non-null values, including nested leaves.
                try:
                    call(item, token, 'GET', f'{mount}/data/{path}')
                except ApiError as error:
                    if error.status != 403:
                        raise RuntimeError('Expected a 403 value-read denial')
                else:
                    raise RuntimeError('Reporting identity can read values; refusing export')
            checks.append(f'{env}: complete inventory; subkeys readable; secret-data GET denied (403) on all three KV mounts')
            reports.append(snapshot)
        finally:
            call(item, token, 'POST', 'auth/token/revoke-self', {})
    denied_item = document['environments']['dev']
    denied_token = call(denied_item, denied_item['root_token'], 'POST', 'auth/token/create',
        {'policies': ['lab-denied'], 'no_default_policy': True, 'ttl': '5m'})['auth']['client_token']
    forbidden.append(denied_token)
    try:
        with local_identity(denied_item['ca'], denied_token):
            denied = drift.collect('dev', cfg=denied_item['settings'], inventory_only=True)
        if denied['complete'] or not any(f.get('http_status') == 403 for f in denied['findings']):
            raise RuntimeError('Denied inventory was not marked incomplete')
        checks.append('Actual denied-token collection correctly reports HTTP 403/unknown/incomplete')
    finally:
        call(denied_item, denied_item['root_token'], 'POST', 'auth/token/revoke', {'token': denied_token})
    comparison = drift.compare_reports(reports)
    rotation = module('lab_rotation', 'rotation-report.py').build([comparison])
    categories = {d['category'] for d in comparison['inventory_differences']}
    if categories != {'policies', 'auth_methods', 'secrets_engines', 'configurations', 'kv_paths'}:
        raise RuntimeError('Expected drift missing from one or more inventory categories')
    counts = rotation['counts']
    if any(counts[status] < 1 for status in ('current', 'overdue', 'missing', 'invalid', 'future_date')):
        raise RuntimeError('Expected rotation statuses not detected')
    checks.extend(['Detected all five inventory categories', 'Detected current/overdue/missing/invalid/future rotation states'])
    # Verify failure interpretation using actual collected artifacts, without altering lab values.
    incomplete = drift.compare_reports(reports[:2])
    if incomplete['complete'] or incomplete['same_supported_inventory'] is not None:
        raise RuntimeError('Missing environment was incorrectly reported as parity')
    checks.append('Missing PROD report correctly produces incomplete/null parity')
    evidence = {'mode': 'live local Vault API collection', 'data': 'generated non-production test data',
                'vault_version': subprocess.check_output(['vault', 'version'], text=True).strip(),
                'collected_at': reports[0]['collected_at'], 'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=BASE, text=True).strip(),
                'source_has_local_changes': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=BASE, text=True).strip()),
                'authentication': 'fresh locally minted read-only tokens; real GitHub federation is validated separately',
                'checks': checks, 'complete': comparison['complete'], 'inventory_difference_count': len(comparison['inventory_differences']),
                'rotation_counts': counts}
    markdown = '> LIVE LOCAL LAB: collected from three real TLS Vault servers with generated non-production data.\n\n'
    markdown += module('lab_renderer', 'render-report.py').render(comparison, rotation)
    exports = {f"{r['environment']}.json": json.dumps(r, indent=2) + '\n' for r in reports}
    exports.update({'comparison.json': json.dumps(comparison, indent=2) + '\n', 'rotation-report.json': json.dumps(rotation, indent=2) + '\n',
                    'evidence.json': json.dumps(evidence, indent=2) + '\n', 'report.md': markdown})
    if any(secret in text for secret in forbidden for text in exports.values()):
        raise RuntimeError('Sensitive test value in export; refusing output')
    output.mkdir(parents=True, exist_ok=True)
    for filename, text in exports.items():
        (output / filename).write_text(text)
    print(f'Real collection passed: {len(comparison["inventory_differences"])} differences; rotation {counts}. Reports: {output}')


def main():
    """Manage this isolated lab; print safe failures and leave unrelated Vaults untouched."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['start', 'report', 'status', 'stop'])
    parser.add_argument('--state-dir', type=Path, default=DEFAULT_STATE)
    parser.add_argument('--output', type=Path, default=BASE / 'examples')
    args = parser.parse_args()
    state = args.state_dir.expanduser().resolve()
    os.umask(0o077)
    try:
        if args.command == 'start':
            start(state)
        elif args.command == 'stop':
            stop(state)
            print('Tracked lab processes stopped; protected logs/certificates retained outside Git.')
        elif args.command == 'report':
            report(state, args.output.resolve())
        else:
            data = json.loads((state / 'state.json').read_text())
            for env, item in data['environments'].items():
                print(f'{env}: {item["settings"]["vault_addr"]}; running={owned_process(item)}')
        return 0
    except Exception:
        print('Local lab failed; check state ownership, ports, Vault version and protected logs. Credentials/responses suppressed.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

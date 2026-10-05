#!/usr/bin/env python3
"""Disposable three-Vault TLS pilot on a hosted runner; real GitHub OIDC, synthetic data."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from common import ApiError, BASE, api, app_definition, authenticate, close_token, settings
from drift import collect, compare_reports


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def terraform_pilot(cfg, root_token, folder, github, checks, forbidden):
    """Local disposable state only; GitHub plan/apply tokens use separate policies."""
    source = folder / 'terraform'
    shutil.copytree(BASE / 'configuration', source, ignore=shutil.ignore_patterns('.terraform', '__pycache__'))
    directory = source / 'configuration'
    main = directory / 'main.tf'
    main.write_text(main.read_text().replace('backend "s3" {}', 'backend "local" {}'))
    def login(kind):
        if github:
            token, owned = authenticate(cfg, kind)
        else:
            token = api(cfg, root_token, 'POST', 'auth/token/create', {'policies': ['demo-' + kind], 'no_default_policy': True, 'ttl': '10m'})['auth']['client_token']
            owned = True
        forbidden.append(token)
        return token, owned
    def tf(args, token):
        variables = {**os.environ, 'VAULT_ADDR': cfg['vault_addr'], 'VAULT_TOKEN': token,
                     'TF_VAR_token_bound_cidrs': '[]', 'TF_IN_AUTOMATION': 'true', 'CHECKPOINT_DISABLE': '1'}
        for key in ('TF_LOG', 'TF_LOG_PATH', 'TF_LOG_PROVIDER', 'TF_LOG_CORE'):
            variables.pop(key, None)
        print('dev: Terraform ' + args[0] + ' with scoped identity')
        result = subprocess.run(['terraform', f'-chdir={directory}', *args], env=variables, capture_output=True, text=True)
        require(result.returncode == 0, 'Terraform pilot ' + args[0] + ' failed; output suppressed')
    token, owned = login('deploy')
    try:
        tf(['init', '-input=false', '-lockfile=readonly'], token)
        tf(['import', '-input=false', 'vault_policy.application', 'demo-app'], token)
        tf(['import', '-input=false', 'vault_approle_auth_backend_role.application', 'auth/approle/role/demo-app'], token)
    finally:
        close_token(cfg, token, owned)
    # Introduce a synthetic configuration change; restore through the reviewed plan.
    api(cfg, root_token, 'POST', 'auth/approle/role/demo-app', {'token_ttl': 7200})
    token, owned = login('plan')
    try:
        tf(['plan', '-input=false', '-out=reviewed.tfplan'], token)
    finally:
        close_token(cfg, token, owned)
    token, owned = login('deploy')
    try:
        tf(['apply', '-input=false', 'reviewed.tfplan'], token)
    finally:
        close_token(cfg, token, owned)
    token, owned = login('plan')
    try:
        tf(['plan', '-input=false', '-detailed-exitcode'], token)
    finally:
        close_token(cfg, token, owned)
    state = (directory / 'terraform.tfstate').read_text()
    require(not any(value in state for value in forbidden), 'Sensitive value in state')
    require('vault_kv_secret' not in state, 'Unexpected secret resource')
    checks.append('dev: scoped plan/apply, configuration restored, subsequent plan unchanged, values absent from disposable state')


def run(local=False, output=Path('pilot-report.json')):
    github = os.environ.get('GITHUB_ACTIONS') == 'true'
    require(local != github, 'Use --local outside Actions; Actions must use real OIDC')
    if github:
        require(os.environ['GITHUB_REPOSITORY'] == 'tekanaid-user/vault-in-vmware', 'Unexpected repository')
        require(os.environ['GITHUB_REF'] == 'refs/heads/main', 'Only main may run this pilot')
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=BASE, text=True).strip()
    app = app_definition(sha)
    policy = (BASE / 'configuration/policy.hcl.tftpl').read_text().replace('${kv_mount}', app['kv_mount']).replace('${secret_path}', app['secret_path'])
    processes = []
    original = {key: os.environ.get(key) for key in ('VAULT_TOKEN', 'VAULT_CACERT', 'VAULT_NAMESPACE')}
    forbidden = []
    healthy = []
    changed = []
    checks = []
    with tempfile.TemporaryDirectory(prefix='vault-oidc-pilot-') as temporary:
        try:
            for env in ('dev', 'uat', 'prod'):
                print(f'{env}: starting isolated TLS Vault')
                folder = Path(temporary) / env
                folder.mkdir(mode=0o700)
                root = uuid.uuid4().hex
                forbidden.append(root)
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0))
                    port = sock.getsockname()[1]
                with (folder / 'server.log').open('w') as log:
                    processes.append(subprocess.Popen(['vault', 'server', '-dev', '-dev-tls', '-dev-no-store-token', f'-dev-tls-cert-dir={folder}', f'-dev-root-token-id={root}', f'-dev-listen-address=127.0.0.1:{port}'], stdout=log, stderr=log))
                cfg = settings(env, live=False)
                cfg.update(vault_addr=f'https://127.0.0.1:{port}', drift_role=f'github-{env}-drift', plan_role=f'github-{env}-plan', deploy_role=f'github-{env}-deploy')
                os.environ['VAULT_CACERT'] = str(folder / 'vault-ca.pem')
                os.environ.pop('VAULT_NAMESPACE', None)
                for _ in range(150):
                    try:
                        api(cfg, root, 'GET', 'sys/health')
                        break
                    except Exception:
                        require(processes[-1].poll() is None, 'Dev server exited')
                        time.sleep(.1)
                else:
                    raise RuntimeError('TLS dev server startup timed out')
                api(cfg, root, 'POST', 'sys/auth/approle', {'type': 'approle'})
                api(cfg, root, 'PUT', f"sys/policies/acl/{app['policy_name']}", {'policy': policy})
                api(cfg, root, 'POST', f"auth/approle/role/{app['approle_name']}", cfg['expected_approle'])
                synthetic = uuid.uuid4().hex
                forbidden.append(synthetic)
                api(cfg, root, 'POST', f"{app['kv_mount']}/data/{app['secret_path']}", {'options': {'cas': 0}, 'data': {field: synthetic for field in app['fields']}})
                api(cfg, root, 'POST', f"{app['kv_mount']}/metadata/{app['secret_path']}", {'custom_metadata': {cfg['rotation_metadata_field']: dt.datetime.now(dt.timezone.utc).date().isoformat()}})
                drift_policy = (BASE / 'bootstrap/drift-policy.hcl').read_text()
                api(cfg, root, 'PUT', 'sys/policies/acl/demo-drift', {'policy': drift_policy})
                for kind in ('plan', 'deploy'):
                    api(cfg, root, 'PUT', 'sys/policies/acl/demo-' + kind, {'policy': (BASE / 'bootstrap' / (kind + '-policy.hcl')).read_text()})
                if github:
                    api(cfg, root, 'POST', 'sys/auth/github', {'type': 'jwt'})
                    api(cfg, root, 'POST', 'auth/github/config', {'oidc_discovery_url': 'https://token.actions.githubusercontent.com', 'bound_issuer': 'https://token.actions.githubusercontent.com'})
                    role = json.loads((BASE / 'bootstrap/github-role.json.example').read_text())
                    role['token_policies'] = ['demo-drift']
                    role['bound_claims'].update(sub='repo:tekanaid-user@37753095/vault-in-vmware@1406319724:environment:vault-pilot', workflow_ref='tekanaid-user/vault-in-vmware/.github/workflows/vault-oidc-pilot.yml@refs/heads/main', event_name='workflow_dispatch')
                    for kind in ('drift', 'plan', 'deploy'):
                        role['token_policies'] = ['demo-' + kind]
                        api(cfg, root, 'POST', f"auth/github/role/{cfg[kind + '_role']}", role)
                    role['token_policies'] = ['demo-drift']
                    negative = json.loads(json.dumps(role))
                    negative['bound_claims']['repository'] = 'untrusted/repository'
                    api(cfg, root, 'POST', 'auth/github/role/rejected-pilot', negative)
                    try:
                        rejected, owned = authenticate({**cfg, 'drift_role': 'rejected-pilot'}, 'drift')
                    except ApiError:
                        checks.append(f'{env}: untrusted repository binding rejected')
                    else:
                        close_token(cfg, rejected, owned)
                        raise RuntimeError('Untrusted binding unexpectedly accepted')
                    print(f'{env}: exchanging GitHub JWT for scoped Vault identity')
                    token, owned = authenticate(cfg, 'drift')
                else:
                    token = api(cfg, root, 'POST', 'auth/token/create', {'policies': ['demo-drift'], 'no_default_policy': True, 'ttl': '10m'})['auth']['client_token']
                    owned = False
                    os.environ['VAULT_TOKEN'] = token
                forbidden.append(token)
                try:
                    subkeys = api(cfg, token, 'GET', f"{app['kv_mount']}/subkeys/{app['secret_path']}")['data']['subkeys']
                    require(all(value is None for value in subkeys.values()), 'Subkeys exposed a value')
                    try:
                        api(cfg, token, 'GET', f"{app['kv_mount']}/data/{app['secret_path']}")
                    except ApiError as error:
                        require(error.status == 403, 'Expected denied secret-data read')
                        checks.append(f'{env}: fields readable; secret values denied (403)')
                    else:
                        raise RuntimeError('Read-only reporting identity could read values')
                finally:
                    close_token(cfg, token, owned)
                if env == 'dev':
                    terraform_pilot(cfg, root, folder, github, checks, forbidden)
                healthy.append(collect(env, cfg=cfg, sha=sha, app=app, policy=policy))
                require(healthy[-1]['complete'] and not healthy[-1]['findings'], 'Baseline unexpectedly differs')
                if env == 'uat':
                    fields = {field: synthetic for field in app['fields'][:-1]}
                    fields['unexpected_field'] = synthetic
                    api(cfg, root, 'POST', f"{app['kv_mount']}/data/{app['secret_path']}", {'data': fields})
                    api(cfg, root, 'POST', f"{app['kv_mount']}/metadata/{app['secret_path']}", {'custom_metadata': {cfg['rotation_metadata_field']: '2020-01-01'}})
                    report = collect(env, cfg=cfg, sha=sha, app=app, policy=policy)
                    require({'field_difference', 'rotation_overdue'} <= {f['kind'] for f in report['findings']}, 'Introduced drift not found')
                    changed.append(report)
                else:
                    changed.append(healthy[-1])
            baseline = compare_reports(healthy)
            drift = compare_reports(changed)
            require(baseline['complete'] and baseline['same_observed_structure'] and not baseline['has_findings'], 'Baseline did not pass')
            require(drift['complete'] and not drift['same_observed_structure'] and drift['has_findings'], 'Drift did not fail parity')
            document = {'mode': 'real GitHub OIDC' if github else 'local scoped tokens (OIDC not tested)', 'checks': checks, 'baseline': baseline, 'introduced_drift': drift, 'disposable': True}
            encoded = json.dumps(document, indent=2)
            require(not any(value in encoded for value in forbidden), 'Sensitive value in report; refusing output')
            output.write_text(encoded + '\n')
            print(f"Passed: three TLS Vaults; {'real OIDC' if github else 'local authentication'}; denied value reads; detected drift/rotation. Report: {output}")
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local', action='store_true', help='Local mechanics only; no OIDC claim')
    parser.add_argument('--output', type=Path, default=Path('pilot-report.json'))
    args = parser.parse_args()
    try:
        run(args.local, args.output)
        return 0
    except (ApiError, RuntimeError) as error:
        print(f'Pilot failed: {error}', file=sys.stderr)
        return 1
    except Exception:
        print('Pilot failed; check TLS, OIDC claim bindings and scoped policies. Details suppressed.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

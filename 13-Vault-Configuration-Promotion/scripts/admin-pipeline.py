"""Internal Terraform plan/apply for the legacy admin configuration, without values."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from common import BASE, REPO, PREFIX, api, ApiError, settings, authenticate, close_token


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tf(root, env, *args, capture=False):
    result = subprocess.run(['terraform', *args], cwd=root, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode and args == ('state', 'list') and 'No state file was found' in result.stderr:
        return ''
    if result.returncode:
        # Provider/server error payloads can contain credentials. Do not echo them.
        raise RuntimeError(f'Terraform {args[0]} failed; detailed output suppressed')
    if capture:
        return result.stdout
    return None


def release(target):
    result = json.loads((BASE / 'environments' / target / 'admin-release.json').read_text())
    sha = result['configuration_ref']
    if not re.fullmatch(r'[0-9a-f]{40}', sha) or sha == '0'*40:
        raise ValueError('Set a reviewed admin-release.json commit first')
    subprocess.run(['git', 'merge-base', '--is-ancestor', sha, 'HEAD'], cwd=REPO, check=True)
    catalog = json.loads(subprocess.check_output(['git', 'show', f'{sha}:{PREFIX}/configuration/admin-catalog.json'], cwd=REPO))
    return result, {'setup_mode': result['setup_mode'],
                    'applications': {x: catalog['applications'][x] for x in result['applications']},
                    'restart_settings': catalog['restart_settings']}


def prepare(root, sha):
    root.mkdir(parents=True)
    for filename in ('main.tf', '.terraform.lock.hcl'):
        root.joinpath(filename).write_bytes(subprocess.check_output(['git', 'show', f'{sha}:{PREFIX}/configuration/admin-setup/{filename}'], cwd=REPO))


def imports(root, env, cfg, token, variables):
    auth = api(cfg, token, 'GET', 'sys/auth')['data']
    mounts = api(cfg, token, 'GET', 'sys/mounts')['data']
    resources = []
    if 'approle/' in auth:
        if auth['approle/']['type'] != 'approle':
            raise ValueError('Existing approle mount has incompatible type')
        resources.append(('vault_auth_backend.approle', 'approle'))
    if variables['setup_mode'] in ('applications', 'both') and 'secret/' in mounts:
        if mounts['secret/']['type'] != 'kv' or mounts['secret/'].get('options', {}).get('version') != '2':
            raise ValueError('Existing secret mount must be KV v2')
        resources.append(('vault_mount.secret[0]', 'secret'))
    selected = list(variables['applications']) if variables['setup_mode'] in ('applications', 'both') else []
    if variables['setup_mode'] in ('restart', 'both'):
        selected.append('restart')
    for name in selected:
        for path, address, identifier in (
            (f'sys/policies/acl/{name}', 'vault_policy.restart[0]' if name == 'restart' else f'vault_policy.application["{name}"]', name),
            (f'auth/approle/role/{name}', 'vault_approle_auth_backend_role.restart[0]' if name == 'restart' else f'vault_approle_auth_backend_role.application["{name}"]', f'auth/approle/role/{name}')):
            try:
                api(cfg, token, 'GET', path)
                resources.append((address, identifier))
            except ApiError as error:
                if error.status != 404:
                    raise
    existing = set(run_tf(root, env, 'state', 'list', capture=True).splitlines())
    for address, identifier in resources:
        if address not in existing:
            run_tf(root, env, 'import', '-input=false', address, identifier)


def plan(root, env, cfg, token, variables, backend):
    root.joinpath('terraform.tfvars.json').write_text(json.dumps(variables))
    run_tf(root, env, 'init', '-input=false', f'-backend-config={backend}')
    imports(root, env, cfg, token, variables)
    run_tf(root, env, 'plan', '-input=false', '-out=approved.tfplan')
    data = json.loads(run_tf(root, env, 'show', '-json', 'approved.tfplan', capture=True))
    changes = data.get('resource_changes', [])
    if any('delete' in change['change']['actions'] for change in changes):
        raise ValueError('Deletion/replacement is blocked; migration requires separate review')
    summary = [{'address': c['address'], 'actions': c['change']['actions']} for c in changes]
    root.joinpath('summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
    return summary


def verify_artifact(root, expected_digest, target, definition, backend):
    if not expected_digest or expected_digest != digest(root/'manifest.json'):
        raise ValueError('Saved plan manifest digest mismatch')
    m = json.loads(root.joinpath('manifest.json').read_text())
    if m['environment'] != target or m['release'] != definition or m['settings_hash'] != digest(BASE/'environments'/target/'settings.json') or m['backend_hash'] != digest(backend):
        raise ValueError('Target, release, settings or backend changed')
    if any(digest(root/name) != checksum for name, checksum in m['files'].items()):
        raise ValueError('Plan/source artifact changed')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['plan', 'apply'])
    p.add_argument('--env', choices=['dev', 'uat', 'prod'], required=True)
    p.add_argument('--digest')
    args = p.parse_args()
    cfg = settings(args.env)
    definition, variables = release(args.env)
    overrides = cfg.get('admin_application_overrides', {})
    if set(overrides) - set(variables['applications']):
        raise ValueError('Environment overrides reference unmanaged applications')
    # The same validator used by the Actions form accepts configuration only.
    import importlib.util
    spec = importlib.util.spec_from_file_location('admin_request', BASE / 'scripts/admin-request.py')
    request = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(request)
    for name, override in overrides.items():
        variables['applications'][name]['settings'] = request.settings(json.dumps(override), variables['applications'][name]['settings'])
    root = BASE / '.admin-run'
    token, owned = authenticate(cfg, 'admin_plan' if args.command == 'plan' else 'admin_deploy')
    env = {k: v for k, v in os.environ.items() if not k.startswith('TF_LOG') and k != 'VAULT_NAMESPACE'} |  {'VAULT_ADDR': cfg['vault_addr'], 'VAULT_TOKEN': token}
    backend = BASE / 'environments' / args.env / 'admin-setup.backend.hcl'
    try:
        if args.command == 'plan':
            shutil.rmtree(root, ignore_errors=True)
            prepare(root, definition['configuration_ref'])
            plan(root, env, cfg, token, variables, backend)
            manifest = {'environment': args.env, 'release': definition, 'settings_hash': digest(BASE / 'environments' / args.env / 'settings.json'),
                        'backend_hash': digest(backend), 'files': {name: digest(root/name) for name in ('approved.tfplan', 'main.tf', '.terraform.lock.hcl', 'terraform.tfvars.json')}}
            root.joinpath('manifest.json').write_text(json.dumps(manifest, sort_keys=True))
            with open(os.environ.get('GITHUB_OUTPUT', os.devnull), 'a') as output:
                output.write(f'manifest_digest={digest(root/"manifest.json")}\n')
        else:
            verify_artifact(root, args.digest, args.env, definition, backend)
            run_tf(root, env, 'init', '-input=false', f'-backend-config={backend}')
            run_tf(root, env, 'apply', '-input=false', 'approved.tfplan')
            print('Configuration applied. Enter or edit application values in Vault UI; no credentials issued.')
    finally:
        close_token(cfg, token, owned)

if __name__ == '__main__':
    main()

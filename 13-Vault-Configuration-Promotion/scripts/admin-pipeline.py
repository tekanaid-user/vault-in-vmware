"""Import managed Vault configuration, save a plan, or apply its approved artifact.

Called by vault-admin-deploy.yml with plan|apply --env dev|uat|prod; apply also
requires --digest from the plan job. Requires Git, Terraform, the reviewed admin
release, settings, backend connectivity/identity and separate admin_plan/admin_
deploy OIDC roles. Works in .admin-run; no application secret values are managed.
Planning may write Terraform state through imports; apply changes Vault config.
A manifest binds target/release/settings/backend/source/plan to the approval.
Deletes/replacements are rejected. Emits a configuration action summary and
manifest_digest via GITHUB_OUTPUT; sensitive Terraform diagnostics are suppressed.
Workflow jobs clean local artifacts; owned Vault tokens are revoked in finally.
See RUNBOOK.md and SCRIPT-REFERENCE.md."""
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
    """Compute a file SHA-256 used to bind the saved artifact to the plan job."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tf(root, env, *args, capture=False):
    """Run Terraform with captured diagnostics; return stdout only when requested.

    An absent initial state is tolerated for state list; other errors are suppressed
    to avoid leaking provider response credentials. No retry/apply fallback occurs."""
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
    """Load selected release/catalog at its SHA; require it to be an ancestor of HEAD."""
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
    """Copy pinned Terraform source and lockfile into a new isolated work directory."""
    root.mkdir(parents=True)
    for filename in ('main.tf', '.terraform.lock.hcl'):
        root.joinpath(filename).write_bytes(subprocess.check_output(['git', 'show', f'{sha}:{PREFIX}/configuration/admin-setup/{filename}'], cwd=REPO))


def imports(root, env, cfg, token, variables):
    """Adopt existing selected mounts/policies/AppRoles into state without duplicating them.

    Only absent resources (404) are skipped. Wrong mount types and denied reads fail;
    imports can update the configured remote state before plan review."""
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
    """Initialize/import, save approved.tfplan, reject delete/replace and write summary.

    summary.json includes allowlisted configuration before/after fields; never use
    this root to manage application values or credentials."""
    root.joinpath('terraform.tfvars.json').write_text(json.dumps(variables))
    run_tf(root, env, 'init', '-input=false', f'-backend-config={backend}')
    imports(root, env, cfg, token, variables)
    run_tf(root, env, 'plan', '-input=false', '-out=approved.tfplan')
    data = json.loads(run_tf(root, env, 'show', '-json', 'approved.tfplan', capture=True))
    changes = data.get('resource_changes', [])
    if any('delete' in change['change']['actions'] for change in changes):
        raise ValueError('Deletion/replacement is blocked; migration requires separate review')
    visible = {'name', 'policy', 'path', 'type', 'options', 'role_name', 'token_policies', 'secret_id_ttl', 'secret_id_num_uses', 'token_ttl', 'token_max_ttl', 'token_num_uses', 'token_bound_cidrs', 'secret_id_bound_cidrs', 'token_no_default_policy', 'default_lease_ttl_seconds', 'max_lease_ttl_seconds'}
    summary = [{'address': c['address'], 'actions': c['change']['actions'],
                'before': {k: v for k, v in (c['change'].get('before') or {}).items() if k in visible},
                'after': {k: v for k, v in (c['change'].get('after') or {}).items() if k in visible}} for c in changes]
    root.joinpath('summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
    return summary


def verify_artifact(root, expected_digest, target, definition, backend):
    """Reject changed target/release/settings/backend/source or mismatched manifest digest."""
    if not expected_digest or expected_digest != digest(root/'manifest.json'):
        raise ValueError('Saved plan manifest digest mismatch')
    m = json.loads(root.joinpath('manifest.json').read_text())
    if m['environment'] != target or m['release'] != definition or m['settings_hash'] != digest(BASE/'environments'/target/'settings.json') or m['backend_hash'] != digest(backend):
        raise ValueError('Target, release, settings or backend changed')
    if any(digest(root/name) != checksum for name, checksum in m['files'].items()):
        raise ValueError('Plan/source artifact changed')

def main():
    """Use plan/apply-specific identities; always close the owned authentication token."""
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

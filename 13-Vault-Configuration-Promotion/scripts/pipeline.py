#!/usr/bin/env python3
"""Internal GitHub Actions plan/apply helper. Security operates the workflow."""
import argparse
import datetime
import getpass
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from common import BASE, PREFIX, REPO, api, app_definition, authenticate, close_token, current_version, read_revision, revision, settings

os.umask(0o077)

def tf(directory, args, cfg, token):
    env = os.environ.copy()
    for name in ('TF_LOG', 'TF_LOG_PATH', 'TF_LOG_PROVIDER', 'TF_LOG_CORE'):
        env.pop(name, None)
    env.update(VAULT_ADDR=cfg['vault_addr'], VAULT_TOKEN=token, TF_IN_AUTOMATION='true', TF_INPUT='false')
    if cfg.get('namespace'):
        env['VAULT_NAMESPACE'] = cfg['namespace']
    else:
        env.pop('VAULT_NAMESPACE', None)
    # Checkpoint/version probes are unnecessary inside a deployment runner.
    env['CHECKPOINT_DISABLE'] = '1'
    subprocess.run(['terraform', f'-chdir={directory}', *args], env=env, check=True)

def copy_configuration(sha, destination):
    entries = subprocess.check_output(['git', 'ls-tree', '-r', sha, '--', f'{PREFIX}/configuration'], cwd=REPO, text=True)
    for entry in entries.splitlines():
        metadata, name = entry.split('\t', 1)
        if metadata.split()[0] not in ('100644', '100755'):
            raise ValueError('Symlinks/submodules are not accepted in configuration')
        rel = Path(name).relative_to(f'{PREFIX}/configuration')
        out = destination / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(subprocess.check_output(['git', 'show', f'{sha}:{name}'], cwd=REPO))

def hashes(directory):
    # Terraform cache and state are excluded; the reviewed source/plan is bound.
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*')) if p.is_file()
            and '.terraform' not in p.parts and p.name != 'run.json'
            and not p.name.startswith('terraform.tfstate')}

def verify_structure(cfg, token, app):
    structure = api(cfg, token, 'GET', f"{app['kv_mount']}/subkeys/{app['secret_path']}")['data']['subkeys']
    if set(structure) != set(app['fields']) or any(value is not None for value in structure.values()):
        raise ValueError('Destination structure differs from Git; review/populate it in Vault UI before promotion')

def staged_request(cfg, token, app, request_id, sha, env):
    if not re.fullmatch(r'[0-9a-f]{32}', request_id or ''):
        raise ValueError('Supply the request ID printed by stage-secret.sh')
    path = f"{cfg['staging_mount']}/metadata/{app['application']}/{request_id}"
    metadata = api(cfg, token, 'GET', path)['data']
    attributes = metadata['custom_metadata']
    if attributes.get('configuration_ref') != sha or attributes.get('environment') != env:
        raise ValueError('Staged request does not match environment/configuration')
    if metadata['current_version'] != 1:
        raise ValueError('Staged payload was modified; stage a new request')
    if datetime.datetime.fromisoformat(attributes['expires_at']) <= datetime.datetime.now(datetime.timezone.utc):
        raise ValueError('Staged request expired; stage a fresh request')
    if current_version(cfg, token, app) != int(attributes['expected_version']):
        raise ValueError('Destination changed since staging; review UI edits and restage')
    structure = api(cfg, token, 'GET', f"{cfg['staging_mount']}/subkeys/{app['application']}/{request_id}", query={'version': 1})['data']['subkeys']
    if set(structure) != set(app['fields']) or any(v is not None for v in structure.values()):
        raise ValueError('Staged field structure does not match the approved flat schema')
    return attributes

def execute(args):
    sha = revision(args.env, getattr(args, 'revision', None))
    app = app_definition(sha)
    cfg = settings(args.env)
    token, owned = authenticate(cfg, 'plan' if args.command == 'plan' else 'deploy')
    try:
        if args.command == 'stage':
            # Read values from terminal only, never command arguments or a file.
            if not sys.stdin.isatty():
                raise ValueError('Stage requires an interactive terminal')
            expected = current_version(cfg, token, app)
            payload = {name: getpass.getpass(f'{args.env} {name} (hidden): ') for name in app['fields']}
            if any(not value for value in payload.values()):
                raise ValueError('Blank values are not accepted by this example')
            request_id = uuid.uuid4().hex
            path = f"{cfg['staging_mount']}/"
            suffix = f"{app['application']}/{request_id}"
            expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
            api(cfg, token, 'POST', path + 'metadata/' + suffix, {
                'delete_version_after': '24h',
                'custom_metadata': {'configuration_ref': sha, 'environment': args.env,
                    'expected_version': str(expected), 'write_version': str(args.write_version), 'expires_at': expires.isoformat()}})
            api(cfg, token, 'POST', path + 'data/' + suffix, {'options': {'cas': 0}, 'data': payload})
            print(f'Request ID: {request_id}\nEnvironment: {args.env}\nConfiguration: {sha}\nDestination version: {expected}')
            return
        if args.command == 'plan':
            operation = args.operation
            if operation == 'configuration':
                verify_structure(cfg, token, app)
            run = BASE / '.runs' / args.env / uuid.uuid4().hex
            run.mkdir(parents=True)
            copy_configuration(sha, run / 'configuration')
            root = run / 'configuration' / operation
            backend = BASE / 'environments' / args.env / f'{operation}.backend.hcl'
            if 'CHANGE_ME' in backend.read_text():
                raise ValueError('Configure approved remote state storage first')
            (run / 'backend.hcl').write_bytes(backend.read_bytes())
            variables = {'token_bound_cidrs': cfg['token_bound_cidrs']} if operation == 'configuration' else {}
            if operation == 'secret-write':
                attributes = staged_request(cfg, token, app, args.request_id, sha, args.env)
                variables = {'request_id': args.request_id, 'staging_mount': cfg['staging_mount'],
                    'expected_version': int(attributes['expected_version']), 'write_version': int(attributes['write_version'])}
            (run / 'inputs.tfvars.json').write_text(json.dumps(variables, indent=2))
            tf(root, ['init', '-input=false', f'-backend-config={run / "backend.hcl"}'], cfg, token)
            tf(root, ['plan', '-input=false', '-lock-timeout=60s', f'-var-file={run / "inputs.tfvars.json"}', f'-out={run / "plan.tfplan"}'], cfg, token)
            plan_data = json.loads(subprocess.check_output(['terraform', f'-chdir={root}', 'show', '-json', str(run / 'plan.tfplan')], text=True))
            for change in plan_data.get('resource_changes', []):
                if 'delete' in change['change']['actions']:
                    raise ValueError('Destructive plans are excluded from this example')
                if operation == 'secret-write' and change['address'] == 'vault_kv_secret_v2.application':
                    old = change['change'].get('before') or {}
                    new = change['change'].get('after') or {}
                    if int(new.get('data_json_wo_version') or 0) <= int(old.get('data_json_wo_version') or 0):
                        raise ValueError('Increase the write version for an intentional secret write')
            manifest = {'environment': args.env, 'configuration_ref': sha, 'operation': operation,
                'request_id': args.request_id, 'settings': cfg, 'hashes': hashes(run)}
            (run / 'run.json').write_text(json.dumps(manifest, indent=2))
            print(f'Review the plan above. Saved run: {run}')
            return
        run = Path(args.run).resolve()
        allowed = (BASE / '.runs' / args.env).resolve()
        if not run.is_relative_to(allowed):
            raise ValueError('Run must belong to the selected environment')
        manifest = json.loads((run / 'run.json').read_text())
        if manifest['environment'] != args.env or manifest['configuration_ref'] != sha or manifest['settings'] != cfg:
            raise ValueError('Environment, release or settings changed; create a fresh plan')
        if manifest['hashes'] != hashes(run):
            raise ValueError('Saved source/plan changed; create a fresh plan')
        if args.approve_environment != args.env:
            raise ValueError('Supply --approve-environment with the exact selected environment after review')
        if manifest['operation'] == 'secret-write':
            staged_request(cfg, token, app, manifest['request_id'], sha, args.env)
        else:
            verify_structure(cfg, token, app)
        root = run / 'configuration' / manifest['operation']
        tf(root, ['init', '-input=false', '-lockfile=readonly', f'-backend-config={run / "backend.hcl"}'], cfg, token)
        print(f'Applying reviewed {manifest["operation"]} plan to {args.env}, configuration {sha}')
        tf(root, ['apply', '-input=false', '-lock-timeout=60s', str(run / 'plan.tfplan')], cfg, token)
        if manifest['operation'] == 'secret-write':
            if current_version(cfg, token, app) != int(json.loads((run / 'inputs.tfvars.json').read_text())['expected_version']) + 1:
                raise ValueError('Destination version differs from the intended write; staging retained')
            actual = api(cfg, token, 'GET', f"{app['kv_mount']}/subkeys/{app['secret_path']}")['data']['subkeys']
            if set(actual) != set(app['fields']):
                raise ValueError('Post-write structure verification failed; staging retained')
            api(cfg, token, 'DELETE', f"{cfg['staging_mount']}/metadata/{app['application']}/{manifest['request_id']}")
        print(f'Completed: {args.env}, {sha}, operation {manifest["operation"]}')
    finally:
        close_token(cfg, token, owned)

parser = argparse.ArgumentParser(description=__doc__)
commands = parser.add_subparsers(dest='command', required=True)
for command in ('stage', 'plan', 'apply'):
    p = commands.add_parser(command)
    p.add_argument('--env', choices=['dev', 'uat', 'prod'], required=True)
    p.add_argument('--revision', help='Full reviewed configuration commit SHA; defaults to release.yaml')
    if command == 'stage':
        p.add_argument('--write-version', type=int, required=True, help='Increase for each intentional write in this environment')
    elif command == 'plan':
        p.add_argument('--operation', choices=['configuration', 'secret-write'], default='configuration')
        p.add_argument('--request-id')
    else:
        p.add_argument('--run', required=True)
        p.add_argument('--approve-environment', required=True)
try:
    arguments = parser.parse_args()
    if arguments.command == 'stage' and arguments.write_version < 1:
        raise ValueError('Write version must be positive')
    execute(arguments)
except (ValueError, RuntimeError, KeyError, OSError, subprocess.CalledProcessError) as error:
    # Never emit raw HTTP bodies or arbitrary exception values from secret reads.
    if isinstance(error, (ValueError, RuntimeError)):
        print(f'Error: {error}', file=sys.stderr)
    else:
        print('Operation failed; check configuration, permissions and Terraform output', file=sys.stderr)
    sys.exit(1)

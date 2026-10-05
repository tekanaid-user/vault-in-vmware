#!/usr/bin/env python3
"""Collect one environment's structure; combine reports offline. No data GETs."""
import argparse
import json
import re
import sys
from common import ApiError, api, app_definition, authenticate, close_token, read_revision, revision, settings

def normalized_policy(text):
    return re.sub(r'\s+', '', re.sub(r'#.*', '', text))

def leaf_fields(structure, prefix=''):
    result = []
    for key, value in structure.items():
        name = prefix + key
        if isinstance(value, dict):
            result.extend(leaf_fields(value, name + '.'))
        else:
            result.append(name)
    return sorted(result)

def collect(env):
    sha = revision(env)
    app = app_definition(sha)
    cfg = settings(env)
    token, owned = authenticate(cfg, 'drift')
    report = {'environment': env, 'configuration_ref': sha, 'expected': app, 'paths': {}, 'findings': []}
    try:
        def paths(prefix):
            try:
                response = api(cfg, token, 'LIST', f"{app['kv_mount']}/metadata/{prefix}")
                items = response['data']['keys']
            except ApiError as error:
                # A 404 is not reliable evidence of absence: some proxies conceal access.
                report['findings'].append({'kind': 'unknown', 'path': prefix, 'http_status': error.status})
                return []
            found = []
            for item in items:
                if not isinstance(item, str) or '..' in item or '/' in item.rstrip('/'):
                    raise ValueError('Unexpected path listing')
                child = prefix + item
                found.extend(paths(child) if item.endswith('/') else [child])
            return found
        scope = app['secret_path'].rsplit('/', 1)[0] + '/'
        observed = paths(scope)
        for path in observed:
            try:
                data = api(cfg, token, 'GET', f"{app['kv_mount']}/subkeys/{path}")['data']
                report['paths'][path] = {'status': 'present', 'fields': leaf_fields(data['subkeys'])}
            except ApiError as error:
                status = 'unknown'
                if error.status == 404:
                    try:
                        metadata = api(cfg, token, 'GET', f"{app['kv_mount']}/metadata/{path}")['data']
                        latest = metadata['versions'][str(metadata['current_version'])]
                        if latest['destroyed'] or latest['deletion_time']:
                            status = 'deleted'
                    except (ApiError, KeyError):
                        pass
                report['paths'][path] = {'status': status}
        actual = report['paths'].get(app['secret_path'])
        if actual is None:
            report['findings'].append({'kind': 'not_observed', 'path': app['secret_path'], 'note': 'Check unknown listing results before declaring missing'})
        elif actual['status'] != 'present':
            report['findings'].append({'kind': actual['status'], 'path': app['secret_path']})
        else:
            missing = sorted(set(app['fields']) - set(actual['fields']))
            extra = sorted(set(actual['fields']) - set(app['fields']))
            if missing or extra:
                report['findings'].append({'kind': 'field_difference', 'missing': missing, 'extra': extra})
        for path in observed:
            if path != app['secret_path']:
                report['findings'].append({'kind': 'extra_path', 'path': path})
        try:
            actual_policy = api(cfg, token, 'GET', f"sys/policies/acl/{app['policy_name']}")['data']['policy']
            expected_policy = read_revision(sha, 'policy.hcl.tftpl').decode().replace('${kv_mount}', app['kv_mount']).replace('${secret_path}', app['secret_path'])
            report['policy'] = normalized_policy(actual_policy)
            if report['policy'] != normalized_policy(expected_policy):
                report['findings'].append({'kind': 'policy_difference_from_git'})
        except ApiError as error:
            report['findings'].append({'kind': 'policy_unknown', 'http_status': error.status})
        # This pilot intentionally covers selected policy/path schema, not every Vault resource.
        return report
    finally:
        close_token(cfg, token, owned)

def compare(files):
    reports = [json.loads(open(path).read()) for path in files]
    if len({r['environment'] for r in reports}) != len(reports):
        raise ValueError('Duplicate environment reports')
    expected_envs = {'dev', 'uat', 'prod'}
    print(json.dumps({'missing_environment_reports': sorted(expected_envs - {r['environment'] for r in reports}),
        'environments': reports,
        'same_selected_release': len({r['configuration_ref'] for r in reports}) == 1,
        'same_observed_structure': len({json.dumps(r['paths'], sort_keys=True) for r in reports}) == 1,
        'same_observed_policy': all('policy' in r for r in reports) and len({r['policy'] for r in reports}) == 1,
        'note': 'Different releases may mean pending promotion. Equal unknown results are not proof of parity. Review findings; no corrections were made.'}, indent=2))

parser = argparse.ArgumentParser(description=__doc__)
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--env', choices=['dev', 'uat', 'prod'])
group.add_argument('--compare', nargs='+', metavar='REPORT_JSON')
try:
    args = parser.parse_args()
    if args.env:
        print(json.dumps(collect(args.env), indent=2))
    else:
        compare(args.compare)
except Exception:
    # Reports contain names/structure, never values or raw failing HTTP responses.
    print('Drift collection failed; check release, connectivity and read-only permissions', file=sys.stderr)
    sys.exit(1)

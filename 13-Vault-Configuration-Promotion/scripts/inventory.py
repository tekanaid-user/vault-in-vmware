"""Vault inventory adapters. No KV data, credentials, issuance or export endpoints."""
import hashlib
import json
from common import ApiError

TOKEN = {'token_policies', 'token_ttl', 'token_max_ttl', 'token_explicit_max_ttl',
         'token_period', 'token_num_uses', 'token_no_default_policy', 'token_type', 'token_bound_cidrs'}
TUNE = {'default_lease_ttl', 'max_lease_ttl', 'audit_non_hmac_request_keys',
        'audit_non_hmac_response_keys', 'listing_visibility', 'passthrough_request_headers',
        'allowed_response_headers', 'token_type', 'force_no_cache', 'allowed_managed_keys',
        'delegated_auth_accessors', 'user_lockout_config', 'plugin_version'}
ROLE_FIELDS = {
    'approle': TOKEN | {'bind_secret_id', 'secret_id_bound_cidrs', 'secret_id_num_uses', 'secret_id_ttl', 'local_secret_ids'},
    'jwt': TOKEN | {'role_type', 'bound_audiences', 'bound_subject', 'bound_claims', 'bound_claims_type',
        'user_claim', 'user_claim_json_pointer', 'groups_claim', 'claim_mappings', 'allowed_redirect_uris',
        'oidc_scopes', 'max_age', 'clock_skew_leeway', 'expiration_leeway', 'not_before_leeway', 'verbose_oidc_logging'},
    'kubernetes': TOKEN | {'bound_service_account_names', 'bound_service_account_namespaces',
        'bound_service_account_namespace_selector', 'audience', 'alias_name_source'},
    'token': {'allowed_policies', 'disallowed_policies', 'allowed_policies_glob', 'disallowed_policies_glob',
        'orphan', 'renewable', 'path_suffix'} | TOKEN,
}
ROLE_FIELDS['oidc'] = ROLE_FIELDS['jwt']
CONFIG_FIELDS = {
    'jwt': {'oidc_discovery_url', 'oidc_discovery_ca_pem', 'oidc_client_id', 'oidc_response_mode',
        'oidc_response_types', 'default_role', 'bound_issuer', 'jwt_supported_algs', 'jwks_url',
        'jwks_ca_pem', 'jwt_validation_pubkeys', 'namespace_in_state', 'provider_config'},
    'ldap': TOKEN | {'url', 'starttls', 'insecure_tls', 'certificate', 'tls_min_version', 'tls_max_version',
        'binddn', 'userdn', 'userattr', 'discoverdn', 'deny_null_bind', 'upndomain', 'userfilter',
        'groupfilter', 'groupdn', 'groupattr', 'case_sensitive_names', 'username_as_alias',
        'use_token_groups', 'max_page_size', 'dereference_aliases', 'request_timeout', 'connection_timeout',
        'anonymous_group_search', 'enable_samaccountname_login', 'rotation_period', 'rotation_schedule',
        'rotation_window', 'disable_automated_rotation'},
    'kubernetes': {'kubernetes_host', 'kubernetes_ca_cert', 'issuer', 'disable_iss_validation',
        'disable_local_ca_jwt', 'pem_keys'},
    'github': {'organization', 'organization_id', 'base_url', 'ttl', 'max_ttl'},
}
CONFIG_FIELDS['oidc'] = CONFIG_FIELDS['jwt']
# provider_config can include provider credentials: deliberately excluded as a whole.
CONFIG_FIELDS['jwt'].discard('provider_config')
PKI_ROLE = {'ttl', 'max_ttl', 'allow_localhost', 'allowed_domains', 'allowed_domains_template',
    'allow_bare_domains', 'allow_subdomains', 'allow_glob_domains', 'allow_any_name', 'enforce_hostnames',
    'allow_ip_sans', 'allowed_uri_sans', 'allowed_other_sans', 'server_flag', 'client_flag', 'code_signing_flag',
    'email_protection_flag', 'key_type', 'key_bits', 'signature_bits', 'use_pss', 'key_usage', 'ext_key_usage',
    'ext_key_usage_oids', 'use_csr_common_name', 'use_csr_sans', 'require_cn', 'basic_constraints_valid_for_non_ca',
    'not_before_duration', 'not_after', 'issuer_ref', 'generate_lease', 'no_store', 'organization',
    'ou', 'country', 'locality', 'province', 'street_address', 'postal_code', 'policy_identifiers'}
TRANSIT_KEY = {'type', 'derived', 'exportable', 'allow_plaintext_backup', 'deletion_allowed',
    'min_decryption_version', 'min_encryption_version', 'auto_rotate_period', 'convergent_encryption',
    'supports_encryption', 'supports_decryption', 'supports_signing', 'supports_derivation', 'imported',
    'allow_import_rotation', 'key_size'}


def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return sorted((canonical(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    return value


def fingerprint(value):
    return hashlib.sha256(json.dumps(canonical(value), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def fingerprints(data, allowed):
    """Only documented non-credential fields; no raw config serialized, even if unexpected."""
    result = {}
    for key in sorted(allowed & data.keys()):
        if key == 'bound_claims' and isinstance(data[key], dict):
            for claim, value in sorted(data[key].items()):
                result['bound_claims/' + claim] = fingerprint(value)
        else:
            result[key] = fingerprint(data[key])
    return result


def scan(cfg, call, policy_normalizer, leaf_fields, rotation_status, today):
    """Inventory configured namespace, including every enabled mount and KV v2 root."""
    result = {key: {} for key in ('policies', 'auth_methods', 'secrets_engines', 'configurations', 'kv_paths')}
    result.update(complete=True, findings=[], coverage={'namespace_scope': 'configured namespace only',
        'unsupported_details': [], 'policy_families': cfg.get('policy_families', ['acl', 'password']),
        'excluded': ['KV v1 values', 'credentials and secret values', 'server storage/seal/TLS configuration',
                     'identity entities/groups', 'child namespaces', 'secret issuance/export endpoints']})

    def unknown(path, error, category='configurations'):
        result['complete'] = False
        result[category][path] = {'status': 'unknown'}
        finding = {'kind': 'inventory_unknown', 'path': path}
        if isinstance(error, ApiError):
            finding['http_status'] = error.status
        result['findings'].append(finding)

    def get(path):
        response = call('GET', path)
        return response.get('data', response)

    def permitted_empty(path, capability):
        # Capability lookup is a read-only POST. A concealed/denied listing is never empty.
        caps = call('POST', 'sys/capabilities-self', {'paths': [path]}).get('data', {})
        effective = caps.get(path, caps.get('capabilities', []))
        return capability in effective or 'root' in effective

    def listing(path, full_names=False):
        try:
            keys = call('LIST', path)['data']['keys']
            if not isinstance(keys, list) or any(not isinstance(k, str) or not k.rstrip('/') or any(part in ('.', '..', '') for part in k.rstrip('/').split('/')) or (not full_names and '/' in k.rstrip('/')) for k in keys):
                raise ValueError('Unexpected listing')
            return sorted(keys)
        except ApiError as error:
            if error.status == 404:
                try:
                    if permitted_empty(path, 'list'):
                        return []
                except (ApiError, RuntimeError, KeyError):
                    pass
            unknown(path, error)
        except (RuntimeError, KeyError, ValueError) as error:
            unknown(path, error)
        return []

    def config(path, allowed):
        try:
            result['configurations'][path] = {'status': 'present', 'fields': fingerprints(get(path), allowed)}
        except ApiError as error:
            # An enabled plugin can have an optional configuration not set yet.
            if error.status == 404:
                try:
                    if permitted_empty(path, 'read'):
                        result['configurations'][path] = {'status': 'not_configured'}
                        return
                except (ApiError, RuntimeError):
                    pass
            unknown(path, error)
        except (RuntimeError, KeyError, TypeError) as error:
            unknown(path, error)

    def collection(prefix, allowed):
        for name in listing(prefix):
            if name.endswith('/'):
                collection(prefix.rstrip('/') + '/' + name.rstrip('/'), allowed)
            else:
                config(prefix.rstrip('/') + '/' + name, allowed)

    for family in result['coverage']['policy_families']:
        if family not in ('acl', 'password', 'rgp', 'egp'):
            raise ValueError('Unsupported policy family')
        for name in listing('sys/policies/' + family, full_names=True):
            path = 'sys/policies/' + family + '/' + name
            if family == 'acl' and name == 'root':
                result['policies']['acl/root'] = {'status': 'builtin'}
                continue
            try:
                policy = get(path)
                allowed = {'policy': policy_normalizer(policy['policy'])}
                if family in ('rgp', 'egp'):
                    allowed.update({k: policy[k] for k in ('enforcement_level', 'paths') if k in policy})
                result['policies'][family + '/' + name] = {'status': 'present', 'fingerprint': fingerprint(allowed)}
            except (ApiError, RuntimeError, KeyError) as error:
                unknown(family + '/' + name, error, 'policies')

    for endpoint, category in (('sys/auth', 'auth_methods'), ('sys/mounts', 'secrets_engines')):
        try:
            mounts = get(endpoint)
        except (ApiError, RuntimeError, KeyError) as error:
            unknown(endpoint, error, category)
            continue
        for mount, data in sorted(mounts.items()):
            if not mount.endswith('/') or not isinstance(data, dict):
                raise ValueError('Unexpected mount inventory')
            kind = data['type']
            result[category][mount] = {'status': 'present', 'type': kind,
                'fields': fingerprints(data, {'type', 'local', 'seal_wrap', 'external_entropy_access', 'options'})}
            tune_path = 'sys/mounts/' + ('auth/' if category == 'auth_methods' else '') + mount + 'tune'
            if kind == 'agent_registry':
                result['coverage']['unsupported_details'].append({'category': category, 'mount': mount, 'type': kind, 'note': 'Built-in registry does not expose mount tuning'})
            else:
                config(tune_path, TUNE)
            if category == 'auth_methods':
                prefix = 'auth/' + mount
                if kind in CONFIG_FIELDS:
                    config(prefix + 'config', CONFIG_FIELDS[kind])
                if kind in ROLE_FIELDS:
                    collection(prefix + ('roles' if kind == 'token' else 'role'), ROLE_FIELDS[kind])
                elif kind == 'ldap':
                    for folder in ('groups', 'users'):
                        collection(prefix + folder, {'policies', 'groups'})
                elif kind == 'userpass':
                    collection(prefix + 'users', TOKEN)
                elif kind == 'github':
                    for folder in ('teams', 'users'):
                        collection(prefix + 'map/' + folder, {'value'})
                else:
                    result['coverage']['unsupported_details'].append({'category': category, 'mount': mount, 'type': kind})
            elif kind == 'kv' and str((data.get('options') or {}).get('version', '1')) == '2':
                config(mount + 'config', {'cas_required', 'max_versions', 'delete_version_after'})
                def walk(prefix):
                    for item in listing(mount + 'metadata/' + prefix):
                        child = prefix + item
                        if item.endswith('/'):
                            walk(child)
                            continue
                        path = mount + child
                        try:
                            metadata = get(mount + 'metadata/' + child)
                            latest = metadata.get('versions', {}).get(str(metadata.get('current_version')), {})
                            if not latest:
                                entry = {'status': 'metadata_only'}
                            elif latest.get('destroyed') or latest.get('deletion_time'):
                                entry = {'status': 'deleted'}
                            else:
                                entry = {'status': 'present', 'fields': leaf_fields(get(mount + 'subkeys/' + child)['subkeys'])}
                            entry['rotation'] = rotation_status(metadata, cfg.get('rotation_metadata_field', 'password_cycle_date'), cfg.get('rotation_max_age_days', 90), today)
                            result['kv_paths'][path] = entry
                            if entry['rotation']['status'] != 'current':
                                result['findings'].append({'kind': 'rotation_' + entry['rotation']['status'], 'path': path})
                            if entry['status'] != 'present':
                                result['findings'].append({'kind': entry['status'] + '_path', 'path': path})
                        except (ApiError, RuntimeError, KeyError, TypeError) as error:
                            unknown(path, error, 'kv_paths')
                walk('')
            elif kind == 'transit':
                collection(mount + 'keys', TRANSIT_KEY)
            elif kind == 'pki':
                config(mount + 'config/urls', {'issuing_certificates', 'crl_distribution_points', 'ocsp_servers', 'enable_templating'})
                config(mount + 'config/crl', {'expiry', 'disable', 'ocsp_disable', 'ocsp_expiry', 'auto_rebuild', 'auto_rebuild_grace_period', 'enable_delta', 'delta_rebuild_interval', 'cross_cluster_revocation', 'unified_crl', 'unified_crl_on_existing_paths'})
                collection(mount + 'roles', PKI_ROLE)
            elif kind == 'database':
                collection(mount + 'roles', {'db_name', 'default_ttl', 'max_ttl', 'credential_type'})
                collection(mount + 'static-roles', {'db_name', 'rotation_period', 'rotation_schedule', 'rotation_window', 'skip_import_rotation', 'credential_type'})
                result['coverage']['unsupported_details'].append({'category': category, 'mount': mount, 'type': kind, 'note': 'Connection configuration and statements excluded: may contain credentials'})
            elif kind not in ('system', 'cubbyhole', 'identity', 'agent_registry'):
                result['coverage']['unsupported_details'].append({'category': category, 'mount': mount, 'type': kind})
    # Per-environment Git baseline protects fields excluded from cross-env parity.
    for path, expected in cfg.get('inventory_expected_fields', {}).items():
        observed = result['configurations'].get(path, {})
        if observed.get('status') != 'present':
            result['findings'].append({'kind': 'configuration_not_observed_from_git', 'path': path})
        else:
            differing = sorted(field for field, value in expected.items()
                               if observed['fields'].get(field) != fingerprint(value))
            if differing:
                result['findings'].append({'kind': 'configuration_difference_from_git', 'path': path, 'fields': differing})
    # Explicit aliases normalize only resource names; they never alter field fingerprints.
    aliases = cfg.get('inventory_resource_aliases', {})
    for category, mapping in aliases.items():
        if category not in result or not isinstance(result[category], dict):
            raise ValueError('Invalid inventory alias category')
        for old, new in mapping.items():
            if old in result[category]:
                if new != old and new in result[category]:
                    raise ValueError('Inventory alias collision')
                result[category][new] = result[category].pop(old)
    result['coverage']['resource_aliases'] = aliases
    result['coverage']['comparison_exceptions'] = cfg.get('inventory_comparison_exceptions', [])
    for exception in result['coverage']['comparison_exceptions']:
        if set(exception) != {'category', 'resource', 'field', 'reason'} or not exception['reason'].strip():
            raise ValueError('Comparison exceptions require exact category/resource/field and a reason')
    return result


def compare(inventories):
    """Field-level differences; no actual configuration values or hashes in findings."""
    differences = []
    ignored = []
    for category in ('policies', 'auth_methods', 'secrets_engines', 'configurations', 'kv_paths'):
        resources = sorted(set().union(*(set(i[category]) for i in inventories.values())))
        for resource in resources:
            entries = {env: i[category].get(resource, {'status': 'absent'}) for env, i in inventories.items()}
            # Rotation dates can legitimately differ; age findings are reported separately.
            comparable = {env: {k: v for k, v in entry.items() if k != 'rotation'} for env, entry in entries.items()}
            exceptions = [i['coverage']['comparison_exceptions'] for i in inventories.values()]
            agreed = [e for e in exceptions[0] if all(e in other for other in exceptions[1:])] if exceptions else []
            for exception in agreed:
                if exception['category'] == category and exception['resource'] == resource:
                    for entry in comparable.values():
                        if isinstance(entry.get('fields'), dict):
                            entry['fields'] = {k: v for k, v in entry['fields'].items() if k != exception['field']}
                    ignored.append(exception)
            if len({json.dumps(v, sort_keys=True) for v in comparable.values()}) > 1:
                fieldsets = [v.get('fields', {}) for v in comparable.values()]
                fields = []
                if all(isinstance(f, dict) for f in fieldsets):
                    fields = [f for f in sorted(set().union(*(set(v) for v in fieldsets))) if len({v.get(f) for v in fieldsets}) > 1]
                differences.append({'category': category, 'resource': resource, 'fields': fields,
                    'environments': {env: e['status'] for env, e in entries.items()}})
    return differences, ignored

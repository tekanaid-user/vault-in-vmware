"""Full inventory: real Vault adapters, permissions, redaction and cross-env parity."""
import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import test_drift as fixtures
from test_drift import BASE, common, drift
import inventory

spec = importlib.util.spec_from_file_location('rotation_report', BASE / 'scripts/rotation-report.py')
rotation_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rotation_report)


class InventoryPureTests(unittest.TestCase):
    def test_allowlist_excludes_credentials_and_arbitrary_fields(self):
        value = {'url': 'ldap://example.invalid', 'bindpass': 'do-not-export', 'client_tls_key': 'private',
                 'unexpected': 'secret'}
        result = inventory.fingerprints(value, inventory.CONFIG_FIELDS['ldap'])
        self.assertEqual(set(result), {'url'})
        self.assertNotIn('example.invalid', json.dumps(result))
        self.assertEqual(inventory.fingerprint(['a', 'b']), inventory.fingerprint(['b', 'a']))

    def test_legacy_reports_cannot_pass_full_inventory(self):
        reports = [{'environment': e, 'complete': True, 'paths': {}, 'findings': [], 'configuration_ref': 'a'} for e in ('dev', 'uat', 'prod')]
        comparison = drift.compare_reports(reports)
        self.assertFalse(comparison['complete'])
        self.assertTrue(comparison['has_findings'])
        self.assertEqual(comparison['missing_inventory_reports'], ['dev', 'prod', 'uat'])

    def test_exceptions_require_three_environment_agreement(self):
        base = {k: {} for k in ('policies', 'auth_methods', 'secrets_engines', 'configurations', 'kv_paths')}
        base['coverage'] = {'comparison_exceptions': []}
        inventories = {env: copy.deepcopy(base) for env in ('dev', 'uat', 'prod')}
        exception = {'category': 'configurations', 'resource': 'auth/github/role/runner',
                     'field': 'bound_claims/sub', 'reason': 'Environment subject is intentionally different'}
        for env, item in inventories.items():
            item['configurations']['auth/github/role/runner'] = {'status': 'present', 'fields': {
                'bound_claims/sub': inventory.fingerprint(env), 'bound_claims/repository': inventory.fingerprint('same')}}
            item['coverage']['comparison_exceptions'] = [exception]
        self.assertEqual(inventory.compare(inventories), ([], [exception]))
        inventories['prod']['coverage']['comparison_exceptions'] = []
        self.assertTrue(inventory.compare(inventories)[0])
        inventories['prod']['coverage']['comparison_exceptions'] = [exception]
        inventories['prod']['configurations']['auth/github/role/runner']['fields']['bound_claims/repository'] = inventory.fingerprint('wrong')
        self.assertEqual(inventory.compare(inventories)[0][0]['fields'], ['bound_claims/repository'])

    def test_rotation_extract_is_values_free_and_flags_missing_environment(self):
        document = {'environment': 'dev', 'complete': True, 'inventory': {'kv_paths': {
            'secret/demo': {'rotation': {'status': 'overdue', 'age_days': 100, 'unexpected': 'secret'}}}}}
        report = rotation_report.build([document])
        self.assertEqual(report['counts']['overdue'], 1)
        self.assertEqual(report['secrets'][0]['age_days'], 100)
        self.assertFalse(report['complete'])
        self.assertNotIn('unexpected', json.dumps(report))
        with self.assertRaises(ValueError):
            rotation_report.build([document, document])


class InventoryLiveTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.LiveTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.LiveTests.tearDownClass.__func__)
    collect = fixtures.LiveTests.collect

    def test_01_all_mounts_paths_policies_and_supported_adapters(self):
        for cfg in self.configs:
            root = self.root
            for mount in ('apps', 'empty', 'nested/secrets'):
                common.api(cfg, root, 'POST', 'sys/mounts/' + mount, {'type': 'kv', 'options': {'version': '2'}})
            # A nested mount needs explicit metadata/subkeys/config/tune rules.
            extra_policy = (BASE / 'bootstrap/drift-policy.hcl').read_text() + '''
path "nested/secrets/metadata" { capabilities = ["list"] }
path "nested/secrets/metadata/*" { capabilities = ["read", "list"] }
path "nested/secrets/subkeys/*" { capabilities = ["read"] }
path "nested/secrets/config" { capabilities = ["read"] }
path "sys/mounts/nested/secrets/tune" { capabilities = ["read"] }
'''
            common.api(cfg, root, 'PUT', 'sys/policies/acl/drift-test', {'policy': extra_policy})
            for mount in ('apps', 'nested/secrets'):
                # Query punctuation in a real key path must not turn into a URL query.
                path = 'outside-demo/nested/app?tag&name'
                common.api(cfg, root, 'POST', mount + '/data/' + path, {'data': {'nested': {'a/b': self.synthetic[0]}, 'empty': {}}})
                common.api(cfg, root, 'POST', mount + '/metadata/' + path, {'custom_metadata': {'password_cycle_date': dt.datetime.now(dt.timezone.utc).date().isoformat()}})
            common.api(cfg, root, 'PUT', 'sys/policies/acl/another-app', {'policy': 'path "apps/data/other" { capabilities = ["read"] }'})
            common.api(cfg, root, 'POST', 'sys/policies/password/application', {'policy': 'length = 20\nrule "charset" { charset = "abcdefghijk123456789" }'})
            common.api(cfg, root, 'POST', 'auth/approle/role/another-app', {'token_policies': ['another-app'], 'token_ttl': 100})
            common.api(cfg, root, 'POST', 'sys/auth/company-ldap', {'type': 'ldap'})
            common.api(cfg, root, 'POST', 'auth/company-ldap/config', {'url': 'ldap://directory.example.invalid', 'binddn': 'cn=vault', 'bindpass': self.synthetic[0], 'userdn': 'ou=users', 'groupdn': 'ou=groups'})
            common.api(cfg, root, 'POST', 'auth/company-ldap/groups/developers', {'policies': ['another-app']})
            common.api(cfg, root, 'POST', 'auth/company-ldap/users/alice', {'groups': ['developers'], 'policies': ['another-app']})
            common.api(cfg, root, 'POST', 'sys/auth/cluster', {'type': 'kubernetes'})
            common.api(cfg, root, 'POST', 'auth/cluster/config', {'kubernetes_host': 'https://127.0.0.1:6443', 'disable_local_ca_jwt': True})
            common.api(cfg, root, 'POST', 'auth/cluster/role/application', {'bound_service_account_names': ['application'], 'bound_service_account_namespaces': ['application'], 'token_policies': ['another-app']})
            common.api(cfg, root, 'POST', 'auth/token/roles/application', {'allowed_policies': ['another-app']})
            common.api(cfg, root, 'POST', 'sys/auth/passwords', {'type': 'userpass'})
            common.api(cfg, root, 'POST', 'auth/passwords/users/alice', {'password': self.synthetic[0], 'token_policies': ['another-app']})
            common.api(cfg, root, 'POST', 'sys/mounts/encryption', {'type': 'transit'})
            common.api(cfg, root, 'POST', 'encryption/keys/application', {'type': 'aes256-gcm96'})
            common.api(cfg, root, 'POST', 'sys/mounts/certificates', {'type': 'pki'})
            common.api(cfg, root, 'POST', 'certificates/roles/application', {'allowed_domains': ['example.invalid'], 'allow_subdomains': True})
        reports = [self.collect(i) for i in range(3)]
        for report in reports:
            self.assertTrue(report['complete'], report['findings'])
            self.assertFalse(report['findings'], report['findings'])
            inv = report['inventory']
            self.assertIn('acl/another-app', inv['policies'])
            self.assertIn('password/application', inv['policies'])
            self.assertIn('auth/approle/role/another-app', inv['configurations'])
            self.assertIn('auth/company-ldap/groups/developers', inv['configurations'])
            self.assertIn('auth/company-ldap/users/alice', inv['configurations'])
            self.assertIn('auth/passwords/users/alice', inv['configurations'])
            self.assertIn('auth/cluster/role/application', inv['configurations'])
            self.assertIn('auth/token/roles/application', inv['configurations'])
            self.assertIn('encryption/keys/application', inv['configurations'])
            self.assertIn('certificates/roles/application', inv['configurations'])
            self.assertIn('empty/', inv['secrets_engines'])
            self.assertEqual(inv['kv_paths']['apps/outside-demo/nested/app?tag&name']['fields'], ['empty', 'nested/a~1b'])
            self.assertIn('nested/secrets/outside-demo/nested/app?tag&name', inv['kv_paths'])
        self.assertTrue(drift.compare_reports(reports)['same_supported_inventory'])
        self.assertTrue(rotation_report.build(reports)['complete'])
        self.assertEqual(rotation_report.build(reports)['counts']['current'], 9)
        # Even the broad inventory identity cannot read KV values or AppRole credentials.
        for cfg, token in zip(self.configs, self.tokens):
            for endpoint in ('apps/data/outside-demo/nested/app?tag&name', 'auth/approle/role/another-app/role-id'):
                with self.assertRaises(common.ApiError) as error:
                    common.api(cfg, token, 'GET', endpoint)
                self.assertEqual(error.exception.status, 403)

    def test_02_all_inventory_categories_compare_between_environments(self):
        cfg = self.configs[1]
        common.api(cfg, self.root, 'PUT', 'sys/policies/acl/another-app', {'policy': 'path "apps/data/other" { capabilities = ["read", "update"] }'})
        common.api(cfg, self.root, 'POST', 'auth/company-ldap/groups/developers', {'policies': ['demo-app']})
        common.api(cfg, self.root, 'POST', 'apps/config', {'cas_required': True})
        common.api(cfg, self.root, 'POST', 'sys/auth/extra-auth', {'type': 'userpass'})
        common.api(cfg, self.root, 'POST', 'sys/mounts/extra-engine', {'type': 'kv', 'options': {'version': '2'}})
        common.api(cfg, self.root, 'POST', 'apps/data/new-path', {'options': {'cas': 0}, 'data': {'unexpected': self.synthetic[1]}})
        report = drift.compare_reports([self.collect(i) for i in range(3)])
        self.assertTrue(report['complete'])
        self.assertFalse(report['same_supported_inventory'])
        self.assertFalse(report['same_observed_structure'])
        self.assertTrue(report['has_findings'])
        self.assertEqual({d['category'] for d in report['inventory_differences']}, {'policies', 'auth_methods', 'secrets_engines', 'configurations', 'kv_paths'})
        fields = next(d['fields'] for d in report['inventory_differences'] if d['resource'] == 'auth/company-ldap/groups/developers')
        self.assertIn('policies', fields)
        self.assertIn('rotation_missing', {f['kind'] for r in report['environments'] for f in r['findings']})

    def test_03_denied_and_hidden_listings_are_unknown_not_empty(self):
        for status in (403, 404):
            original_api = drift.api
            def denied(cfg, token, method, path, payload=None):
                if path == 'apps/metadata/' or (path == 'sys/capabilities-self' and payload['paths'] == ['apps/metadata/']):
                    raise common.ApiError(status, path)
                return original_api(cfg, token, method, path, payload)
            with patch.object(drift, 'api', side_effect=denied), patch.object(drift, 'authenticate', return_value=(self.tokens[0], False)):
                report = drift.collect('dev', cfg=self.configs[0], sha='a'*40, app=self.app, policy=self.policy)
            self.assertFalse(report['complete'])
            self.assertTrue(any(f['path'] == 'apps/metadata/' for f in report['findings']))
            self.assertIsNone(drift.compare_reports([report])['same_supported_inventory'])

    def test_04_unsupported_engine_details_are_declared(self):
        cfg = self.configs[0]
        common.api(cfg, self.root, 'POST', 'sys/mounts/legacy', {'type': 'kv', 'options': {'version': '1'}})
        common.api(cfg, self.root, 'POST', 'legacy/a', {'password': self.synthetic[0]})
        report = self.collect(0)
        self.assertTrue(report['complete'])
        self.assertIn('legacy/', report['inventory']['secrets_engines'])
        self.assertNotIn('legacy/a', report['inventory']['kv_paths'])
        self.assertIn('legacy/', {x['mount'] for x in report['inventory']['coverage']['unsupported_details']})



class BaselineTests(unittest.TestCase):
    def test_ignored_subject_still_checks_git_baseline(self):
        def call(method, path, payload=None):
            if path == 'sys/auth':
                return {'data': {'github/': {'type': 'jwt'}}}
            if path == 'sys/mounts':
                return {'data': {}}
            if method == 'LIST':
                return {'data': {'keys': ['runner'] if path == 'auth/github/role' else []}}
            if path == 'auth/github/role/runner':
                return {'data': {'bound_claims': {'sub': 'wrong-subject'}}}
            return {'data': {}}
        cfg = {'inventory_expected_fields': {'auth/github/role/runner': {'bound_claims/sub': 'expected-subject'}}}
        report = inventory.scan(cfg, call, drift.normalized_policy, drift.leaf_fields, drift.rotation_status, dt.date(2026, 10, 5))
        self.assertEqual(report['findings'], [{'kind': 'configuration_difference_from_git', 'path': 'auth/github/role/runner', 'fields': ['bound_claims/sub']}])

    def test_database_and_sentinel_adapters_never_request_credentials(self):
        calls = []
        def call(method, path, payload=None):
            calls.append((method, path))
            if path == 'sys/auth':
                return {'data': {}}
            if path == 'sys/mounts':
                return {'data': {'db/': {'type': 'database'}}}
            if method == 'LIST':
                return {'data': {'keys': ['application']}}
            if path.startswith('sys/policies/'):
                return {'data': {'policy': 'main = rule { true }', 'enforcement_level': 'hard-mandatory', 'paths': ['secret/*']}}
            if path.startswith('db/'):
                return {'data': {'db_name': 'demo', 'default_ttl': 100, 'rotation_period': 100,
                                 'creation_statements': ['password=never-export'], 'password': 'never-export'}}
            return {'data': {}}
        report = inventory.scan({'policy_families': ['rgp', 'egp']}, call, drift.normalized_policy, drift.leaf_fields, drift.rotation_status, dt.date(2026, 10, 5))
        self.assertTrue(report['complete'])
        self.assertEqual(set(report['policies']), {'rgp/application', 'egp/application'})
        self.assertIn('db/roles/application', report['configurations'])
        self.assertIn('db/static-roles/application', report['configurations'])
        self.assertFalse(any(path.startswith('db/config') for method, path in calls))
        self.assertNotIn('never-export', json.dumps(report))


if __name__ == '__main__':
    unittest.main()

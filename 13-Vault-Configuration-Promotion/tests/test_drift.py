"""Integration tests: three isolated loopback Vault dev processes, synthetic values only."""
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'scripts'))
import common
import drift
spec = importlib.util.spec_from_file_location('creator', BASE / 'scripts/create-secret.py')
creator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(creator)


class PureTests(unittest.TestCase):
    def test_subkeys_never_accept_values(self):
        self.assertEqual(drift.leaf_fields({'a': {'b': None}, 'c': None}), ['a/b', 'c'])
        with self.assertRaises(ValueError):
            drift.leaf_fields({'password': 'synthetic-value'})

    def test_rotation(self):
        today = dt.date(2026, 10, 5)
        for value, status in [(None, 'missing'), ('not-a-date', 'invalid'), ('2027-01-01', 'future_date'), ('2026-01-01', 'overdue'), ('2026-10-01', 'current')]:
            self.assertEqual(drift.rotation_status({'custom_metadata': {'cycle': value}}, 'cycle', 90, today)['status'], status)

    def test_incomplete_is_not_parity(self):
        reports = [{'environment': e, 'configuration_ref': 'a', 'paths': {}, 'findings': [], 'complete': False} for e in ('dev', 'uat', 'prod')]
        self.assertIsNone(drift.compare_reports(reports)['same_observed_structure'])
        self.assertEqual(drift.compare_reports([])['missing_environment_reports'], ['dev', 'prod', 'uat'])
        self.assertFalse(drift.compare_reports(reports[:1])['complete'])
        with self.assertRaises(ValueError):
            drift.compare_reports([reports[0], reports[0]])

    def test_policy_whitespace_in_quotes_is_significant(self):
        self.assertNotEqual(drift.normalized_policy('path "a b" {}'), drift.normalized_policy('path "ab" {}'))
        self.assertEqual(drift.normalized_policy('path "a" {} # note'), drift.normalized_policy('path "a" {}'))
        self.assertNotEqual(drift.leaf_fields({'a/b': None}), drift.leaf_fields({'a': {'b': None}}))
        self.assertNotEqual(drift.leaf_fields({'empty': {}}), drift.leaf_fields({}))


@unittest.skipUnless(shutil.which('vault'), 'vault CLI required')
class LiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='vault-drift-tests-')
        cls.processes = []
        cls.configs = []
        cls.tokens = []
        cls.root = uuid.uuid4().hex
        cls.app = common.app_definition()
        cls.policy = (BASE / 'configuration/policy.hcl.tftpl').read_text().replace('${kv_mount}', cls.app['kv_mount']).replace('${secret_path}', cls.app['secret_path'])
        cls.synthetic = []
        try:
            for index, env in enumerate(('dev', 'uat', 'prod')):
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0))
                    port = sock.getsockname()[1]
                log = open(Path(cls.temp.name) / f'{env}.log', 'w')
                process = subprocess.Popen(['vault', 'server', '-dev', '-dev-no-store-token', f'-dev-root-token-id={cls.root}', f'-dev-listen-address=127.0.0.1:{port}'], stdout=log, stderr=log)
                log.close()
                cls.processes.append(process)
                cfg = json.loads((BASE / 'environments' / env / 'settings.json').read_text())
                cfg['vault_addr'] = f'http://127.0.0.1:{port}'
                for _ in range(100):
                    try:
                        common.api(cfg, cls.root, 'GET', 'sys/health')
                        break
                    except Exception:
                        if process.poll() is not None:
                            raise RuntimeError('Dev server exited; log suppressed')
                        time.sleep(.1)
                else:
                    raise RuntimeError('Dev server did not start')
                common.api(cfg, cls.root, 'POST', 'sys/auth/approle', {'type': 'approle'})
                common.api(cfg, cls.root, 'PUT', 'sys/policies/acl/demo-app', {'policy': cls.policy})
                common.api(cfg, cls.root, 'POST', 'auth/approle/role/demo-app', cfg['expected_approle'])
                value = f'synthetic-{env}-{uuid.uuid4().hex}'
                cls.synthetic.append(value)
                common.api(cfg, cls.root, 'POST', 'secret/data/demo/app', {'data': {'username': value, 'password': value}})
                common.api(cfg, cls.root, 'POST', 'secret/metadata/demo/app', {'custom_metadata': {'password_cycle_date': dt.datetime.now(dt.timezone.utc).date().isoformat(), 'unexpected_metadata': value}})
                common.api(cfg, cls.root, 'PUT', 'sys/policies/acl/drift-test', {'policy': (BASE / 'bootstrap/drift-policy.hcl').read_text()})
                token = common.api(cfg, cls.root, 'POST', 'auth/token/create', {'policies': ['drift-test'], 'no_default_policy': True, 'ttl': '10m'})['auth']['client_token']
                cls.configs.append(cfg)
                cls.tokens.append(token)
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        for process in cls.processes:
            process.terminate()
        for process in cls.processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        cls.temp.cleanup()

    def collect(self, index):
        calls = []
        def observed_api(cfg, token, method, path, payload=None):
            calls.append((method, path))
            return common.api(cfg, token, method, path, payload)
        with patch.object(drift, 'authenticate', return_value=(self.tokens[index], False)), patch.object(drift, 'api', side_effect=observed_api):
            result = drift.collect(('dev', 'uat', 'prod')[index], cfg=self.configs[index], sha='a' * 40, app=self.app, policy=self.policy)
        self.assertTrue(all(method in ('GET', 'LIST') and '/data/' not in path for method, path in calls))
        encoded = json.dumps(result)
        for value in [*self.synthetic, self.root, *self.tokens]:
            self.assertNotIn(value, encoded)
        return result

    def test_01_identical_structure_different_values(self):
        reports = [self.collect(i) for i in range(3)]
        self.assertTrue(all(r['complete'] for r in reports))
        self.assertTrue(all(not r['findings'] for r in reports), reports)
        result = drift.compare_reports(reports)
        self.assertTrue(result['same_observed_structure'])
        self.assertTrue(result['all_policies_match_selected_git'])

    def test_02_read_identity_cannot_read_values(self):
        for cfg, token in zip(self.configs, self.tokens):
            with self.assertRaises(common.ApiError) as error:
                common.api(cfg, token, 'GET', 'secret/data/demo/app')
            self.assertEqual(error.exception.status, 403)
        cfg = self.configs[0]
        policy = (BASE / 'bootstrap/developer-keys-policy.hcl').read_text()
        common.api(cfg, self.root, 'PUT', 'sys/policies/acl/keys-test', {'policy': policy})
        token = common.api(cfg, self.root, 'POST', 'auth/token/create', {'policies': ['keys-test'], 'no_default_policy': True})['auth']['client_token']
        self.assertEqual(common.api(cfg, token, 'GET', 'secret/subkeys/demo/app')['data']['subkeys'], {'username': None, 'password': None})
        with self.assertRaises(common.ApiError):
            common.api(cfg, token, 'GET', 'secret/data/demo/app')
        command_env = {**os.environ, 'VAULT_ADDR': cfg['vault_addr'], 'VAULT_TOKEN': token}
        cli = subprocess.run(['vault', 'read', '-format=json', 'secret/subkeys/demo/app'], env=command_env, capture_output=True, text=True)
        self.assertEqual(cli.returncode, 0)
        self.assertEqual(json.loads(cli.stdout)['data']['subkeys'], {'username': None, 'password': None})

    def test_03_detect_drift_and_rotation(self):
        cfg = self.configs[1]
        common.api(cfg, self.root, 'POST', 'secret/data/demo/app', {'data': {'username': self.synthetic[1], 'extra': self.synthetic[1]}})
        common.api(cfg, self.root, 'POST', 'secret/metadata/demo/app', {'custom_metadata': {'password_cycle_date': '2020-01-01'}})
        common.api(cfg, self.root, 'POST', 'secret/data/demo/old-name', {'data': {'nested': {'field': self.synthetic[1]}}})
        common.api(cfg, self.root, 'PUT', 'sys/policies/acl/demo-app', {'policy': 'path "secret/data/demo/app" { capabilities = ["read", "update"] }'})
        common.api(cfg, self.root, 'POST', 'auth/approle/role/demo-app', {'token_ttl': 7200})
        common.api(cfg, self.root, 'POST', 'secret/config', {'cas_required': True})
        report = self.collect(1)
        kinds = {f['kind'] for f in report['findings']}
        self.assertTrue({'field_difference', 'extra_path', 'rotation_overdue', 'rotation_missing', 'policy_difference_from_git', 'approle_difference_from_git', 'kv_config_difference_from_git'} <= kinds)
        self.assertFalse(drift.compare_reports([self.collect(i) for i in range(3)])['same_observed_structure'])

    def test_04_deleted_and_permissions_unknown(self):
        cfg = self.configs[2]
        common.api(cfg, self.root, 'DELETE', 'secret/data/demo/app')
        self.assertEqual(self.collect(2)['paths']['demo/app']['status'], 'deleted')
        common.api(cfg, self.root, 'PUT', 'sys/policies/acl/noaccess-test', {'policy': 'path "secret/*" { capabilities = ["deny"] }'})
        token = common.api(cfg, self.root, 'POST', 'auth/token/create', {'policies': ['noaccess-test'], 'no_default_policy': True})['auth']['client_token']
        with patch.object(drift, 'authenticate', return_value=(token, False)):
            report = drift.collect('prod', cfg=cfg, sha='a'*40, app=self.app, policy=self.policy)
        self.assertFalse(report['complete'])
        self.assertIn('listing_unknown', {f['kind'] for f in report['findings']})

    def test_05_create_is_safe_and_does_not_overwrite(self):
        cfg = self.configs[0]
        app = {**self.app, 'secret_path': 'demo/new'}
        policy = (BASE / 'bootstrap/secret-creator-policy.hcl').read_text().replace('demo/app', 'demo/new')
        common.api(cfg, self.root, 'PUT', 'sys/policies/acl/create-test', {'policy': policy})
        token = common.api(cfg, self.root, 'POST', 'auth/token/create', {'policies': ['create-test'], 'no_default_policy': True})['auth']['client_token']
        values = {'username': 'synthetic-user', 'password': 'synthetic-password'}
        creator.create(cfg, token, app, values)
        with self.assertRaises(common.ApiError):
            creator.create(cfg, token, app, values)
        with self.assertRaises(common.ApiError):
            common.api(cfg, token, 'GET', 'secret/data/demo/new')

    @unittest.skipUnless(shutil.which('terraform'), 'terraform CLI required')
    def test_06_terraform_apply_and_state_without_values(self):
        fixture = Path(self.temp.name) / 'terraform-fixture'
        shutil.copytree(BASE / 'configuration', fixture, ignore=shutil.ignore_patterns('.terraform'))
        root = fixture / 'configuration'
        main = root / 'main.tf'
        main.write_text(main.read_text().replace('backend "s3" {}', 'backend "local" {}'))
        env = {**os.environ, 'VAULT_ADDR': self.configs[0]['vault_addr'], 'VAULT_TOKEN': self.root,
               'TF_VAR_token_bound_cidrs': '[]', 'TF_IN_AUTOMATION': 'true', 'CHECKPOINT_DISABLE': '1'}
        for key in ('VAULT_NAMESPACE', 'TF_LOG', 'TF_LOG_PATH', 'TF_LOG_PROVIDER', 'TF_LOG_CORE'):
            env.pop(key, None)
        for arguments in (['init', '-input=false', '-lockfile=readonly'],
                          ['import', '-input=false', 'vault_policy.application', 'demo-app'],
                          ['import', '-input=false', 'vault_approle_auth_backend_role.application', 'auth/approle/role/demo-app'],
                          ['plan', '-input=false', '-out=reviewed.tfplan'],
                          ['apply', '-input=false', 'reviewed.tfplan'],
                          ['plan', '-input=false', '-detailed-exitcode']):
            result = subprocess.run(['terraform', f'-chdir={root}', *arguments], env=env, capture_output=True, text=True)
            safe_error = result.stderr
            for value in [*self.synthetic, self.root, *self.tokens]:
                safe_error = safe_error.replace(value, '[REDACTED]')
            self.assertEqual(result.returncode, 0, f'Terraform {arguments[0]} failed: {safe_error}')
        state = (root / 'terraform.tfstate').read_text()
        for value in [*self.synthetic, self.root, *self.tokens]:
            self.assertNotIn(value, state)
        self.assertNotIn('vault_kv_secret', state)

    def test_07_cli_compare_exit_codes(self):
        files = []
        for index in range(3):
            p = Path(self.temp.name) / f'report-{index}.json'
            p.write_text(json.dumps(self.collect(index)))
            files.append(str(p))
        cli = subprocess.run([sys.executable, str(BASE / 'scripts/drift.py'), '--compare', *files, '--fail-on-findings'], capture_output=True, text=True)
        self.assertEqual(cli.returncode, 2)
        self.assertTrue(json.loads(cli.stdout)['has_findings'])
        incomplete = subprocess.run([sys.executable, str(BASE / 'scripts/drift.py'), '--compare', files[0], '--fail-on-findings'], capture_output=True, text=True)
        self.assertEqual(incomplete.returncode, 3)
        self.assertIsNone(json.loads(incomplete.stdout)['same_observed_structure'])


if __name__ == '__main__':
    unittest.main()

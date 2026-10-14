"""Prove the repeatable lab collects real TLS Vault APIs through the actual CLI.

Uses separate random-port fixtures and private temporary state, leaving an
operator's running demo untouched. Covers repeatability, real differences,
value-read denial, incomplete evidence and safe settings overrides.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'scripts'))
import common

spec = importlib.util.spec_from_file_location('local_demo', BASE / 'scripts/local-demo.py')
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class SettingsFileTests(unittest.TestCase):
    def test_settings_override_still_rejects_http_and_namespaces(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'settings.json'
            p.write_text(json.dumps({'vault_addr': 'https://127.0.0.1:18520'}))
            self.assertEqual(common.settings('dev', filename=p)['vault_addr'], 'https://127.0.0.1:18520')
            for data in ({'vault_addr': 'http://127.0.0.1:18520'}, {'vault_addr': 'https://127.0.0.1:18520', 'namespace': 'not-supported'}):
                p.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    common.settings('dev', filename=p)


@unittest.skipUnless(shutil.which('vault'), 'Vault CLI required for live TLS lab')
class LocalLabTests(unittest.TestCase):
    def test_real_cli_collection_repeats_and_never_exports_credentials(self):
        reserved, ports = [], {}
        try:
            for env in ('dev', 'uat', 'prod'):
                while True:
                    first = socket.socket()
                    first.bind(('127.0.0.1', 0))
                    port = first.getsockname()[1]
                    second = socket.socket()
                    try:
                        second.bind(('127.0.0.1', port + 1))
                    except OSError:
                        first.close()
                        second.close()
                        continue
                    reserved.extend([first, second])
                    ports[env] = port
                    break
        finally:
            for sock in reserved:
                sock.close()
        with tempfile.TemporaryDirectory(prefix='vault-lab-tests-') as d:
            state, output = Path(d), Path(d) / 'reports'
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    lab.start(state, ports)
                    initial = json.loads((state / 'state.json').read_text())
                    lab.start(state, ports)
                    self.assertEqual(initial, json.loads((state / 'state.json').read_text()))
                    lab.report(state, output)
                    first = json.loads((output / 'comparison.json').read_text())
                    lab.report(state, output)
                second = json.loads((output / 'comparison.json').read_text())
                self.assertTrue(second['complete'])
                self.assertTrue(second['has_findings'])
                self.assertEqual(first['inventory_differences'], second['inventory_differences'])
                self.assertEqual({d['category'] for d in second['inventory_differences']},
                                 {'policies', 'auth_methods', 'secrets_engines', 'configurations', 'kv_paths'})
                evidence = json.loads((output / 'evidence.json').read_text())
                self.assertTrue(any('HTTP 403/unknown/incomplete' in check for check in evidence['checks']))
                self.assertTrue(all(evidence['rotation_counts'][status] for status in ('current', 'missing', 'overdue', 'invalid', 'future_date')))
                for sensitive in initial['sensitive_test_values']:
                    for p in output.iterdir():
                        self.assertNotIn(sensitive, p.read_text())
            finally:
                lab.stop(state)
            self.assertTrue(all(not lab.owned_process(item) for item in initial['environments'].values()))


if __name__ == '__main__':
    unittest.main()

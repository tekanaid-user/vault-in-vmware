"""Onboarding boundaries: claims-only, exact roles, token cleanup and report interpretation."""
import base64
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'scripts'))
import drift
import inventory


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, BASE / 'scripts' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


oidc = module('oidc_check', 'oidc-check.py')
renderer = module('render_report', 'render-report.py')


class OnboardingTests(unittest.TestCase):
    def test_claims_inspection_does_not_connect_to_vault_or_export_token(self):
        payload = {'sub': 'repo:example/repo:environment:dev-drift', 'aud': 'vault-demo',
                   'unexpected': 'do-not-export', 'actor': 'not-needed'}
        jwt = 'header.' + base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=') + '.signature'
        with patch.object(oidc, 'settings', return_value={'oidc_audience': 'vault-demo'}) as cfg, \
             patch.object(oidc, 'github_jwt', return_value=jwt), \
             patch.object(oidc, 'api', side_effect=AssertionError('no Vault connection')):
            report = oidc.check('dev', claims_only=True)
        cfg.assert_called_once_with('dev', live=False)
        self.assertEqual(report['claims'], {k: payload[k] for k in ('aud', 'sub')})
        self.assertNotIn(jwt, json.dumps(report))
        self.assertNotIn('do-not-export', json.dumps(report))

    def test_authentication_uses_drift_role_and_revokes_after_read_failure(self):
        cfg = {'vault_addr': 'https://vault.example.invalid'}
        with patch.dict('os.environ', {'GITHUB_ACTIONS': 'true'}), \
             patch.object(oidc, 'settings', return_value=cfg), \
             patch.object(oidc, 'authenticate', return_value=('private-token', True)) as auth, \
             patch.object(oidc, 'api', side_effect=RuntimeError('read failed')), \
             patch.object(oidc, 'close_token') as revoke:
            with self.assertRaises(RuntimeError):
                oidc.check('dev')
        auth.assert_called_once_with(cfg, 'drift')
        revoke.assert_called_once_with(cfg, 'private-token', True)

    def test_local_token_cannot_masquerade_as_github_federation(self):
        with patch.dict('os.environ', {'GITHUB_ACTIONS': 'false'}), \
             patch.object(oidc, 'settings', return_value={}), \
             patch.object(oidc, 'authenticate') as auth:
            with self.assertRaises(ValueError):
                oidc.check('dev')
            auth.assert_not_called()

    def test_inventory_only_parity_does_not_claim_git_compliance(self):
        inv = {k: {} for k in ('policies', 'auth_methods', 'secrets_engines', 'configurations', 'kv_paths')}
        inv['coverage'] = {'comparison_exceptions': [], 'unsupported_details': []}
        reports = [{'environment': env, 'configuration_ref': None, 'paths': {}, 'findings': [],
                    'complete': True, 'inventory': copy.deepcopy(inv)} for env in ('dev', 'uat', 'prod')]
        report = drift.compare_reports(reports)
        self.assertTrue(report['same_supported_inventory'])
        self.assertIsNone(report['same_selected_release'])
        self.assertIsNone(report['all_policies_match_selected_git'])
        reports[0]['inventory']['kv_paths']['secret/app/config'] = {'status': 'present', 'fields': ['password', 'username']}
        reports[1]['inventory']['kv_paths']['secret/app/config'] = {'status': 'present', 'fields': ['username']}
        reports[2]['inventory']['kv_paths']['secret/app/config'] = {'status': 'present', 'fields': ['username']}
        changed = drift.compare_reports(reports)
        self.assertEqual(changed['inventory_differences'][0]['fields'], ['password'])
        changed['inventory_differences'][0]['resource'] = 'secret/app|<config>'
        changed['hidden_token'] = 'must-not-render'
        output = renderer.render(changed, {'secrets': []})
        self.assertIn('secret/app&#124;&lt;config&gt;', output)
        self.assertNotIn('must-not-render', output)


if __name__ == '__main__':
    unittest.main()

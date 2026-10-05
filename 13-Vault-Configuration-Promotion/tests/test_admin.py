"""Actual admin helper with disposable Vault and portable saved plan, synthetic data."""
import contextlib
import importlib.util
import io
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
import uuid
from unittest.mock import patch
from types import SimpleNamespace

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE/'scripts'))
import common

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, BASE/'scripts'/file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

request = load('admin_request', 'admin-request.py')
pipeline = load('admin_pipeline', 'admin-pipeline.py')
credentials = load('restart_credentials', 'restart-credentials.py')

class Inputs(unittest.TestCase):
    def test_names_and_values_rejected(self):
        self.assertEqual(request.names('webapp database'), ['webapp', 'database'])
        for raw in ('root', 'restart', '../app', 'a;curl', '$(id)', 'a a', ''):
            with self.assertRaises(ValueError): request.names(raw)
        with self.assertRaises(ValueError): request.settings('{"password":"value"}', request.DEFAULT)
        with self.assertRaises(ValueError): request.settings('{"token_bound_cidrs":["wrong"]}', request.DEFAULT)
        with self.assertRaises(ValueError): request.settings('{"token_ttl":true}', request.DEFAULT)

    def test_request_catalog_then_reviewed_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp); base=repo/'13-Vault-Configuration-Promotion'
            (base/'configuration').mkdir(parents=True)
            (base/'environments/dev').mkdir(parents=True)
            catalog_path=base/'configuration/admin-catalog.json'
            catalog_path.write_text((BASE/'configuration/admin-catalog.json').read_text())
            (base/'environments/dev/admin-release.json').write_text(json.dumps({'configuration_ref':'0'*40,'setup_mode':'applications','applications':[]}))
            args=SimpleNamespace(operation='configure',environment='dev',setup_mode='both',applications='webapp database',keys='api-key db-password',application_settings='{}',restart_settings='{}',configuration_ref='',ticket='SYNTHETIC-TEST')
            with patch.object(request,'BASE',base),patch.object(request,'REPO',repo):
                path,catalog=request.generate(args)
                self.assertEqual(set(catalog['applications']),{'webapp','database'})
                path.write_text(json.dumps(catalog))
                subprocess.run(['git','init','-q','-b','main'],cwd=repo,check=True)
                subprocess.run(['git','add','.'],cwd=repo,check=True)
                subprocess.run(['git','-c','user.name=Synthetic Test','-c','user.email=test@example.invalid','commit','-qm','Synthetic fixture'],cwd=repo,check=True)
                sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
                subprocess.run(['git','update-ref','refs/remotes/origin/main',sha],cwd=repo,check=True)
                args.operation='promote';args.configuration_ref=sha
                target,definition=request.generate(args)
                self.assertEqual(definition['configuration_ref'],sha)
                self.assertEqual(definition['setup_mode'],'both')
                self.assertEqual(definition['applications'],['database','webapp'])
                target.write_text(json.dumps(definition))
                args.setup_mode='applications';args.applications='webapp'
                _,again=request.generate(args)
                self.assertEqual(again['setup_mode'],'both')
                self.assertEqual(again['applications'],['database','webapp'])

    def test_community_rejects_namespaces(self):
        with self.assertRaises(ValueError):
            common.api({'vault_addr':'http://127.0.0.1:1','namespace':'unsupported'},'token','GET','sys/mounts')

    def test_artifact_integrity_and_wrong_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); root=base/'artifact'; root.mkdir()
            settings_dir=base/'environments/dev'; settings_dir.mkdir(parents=True)
            (settings_dir/'settings.json').write_text('{}')
            backend=base/'backend'; backend.write_text('backend')
            (root/'approved.tfplan').write_text('saved-plan')
            definition={'configuration_ref':'a'*40}
            m={'environment':'dev','release':definition,'settings_hash':pipeline.digest(settings_dir/'settings.json'),'backend_hash':pipeline.digest(backend),'files':{'approved.tfplan':pipeline.digest(root/'approved.tfplan')}}
            (root/'manifest.json').write_text(json.dumps(m)); checksum=pipeline.digest(root/'manifest.json')
            with patch.object(pipeline,'BASE',base):
                pipeline.verify_artifact(root,checksum,'dev',definition,backend)
                with self.assertRaises(ValueError): pipeline.verify_artifact(root,checksum,'prod',definition,backend)
                with self.assertRaises(ValueError): pipeline.verify_artifact(root,'wrong','dev',definition,backend)
                (root/'approved.tfplan').write_text('tampered')
                with self.assertRaises(ValueError): pipeline.verify_artifact(root,checksum,'dev',definition,backend)

@unittest.skipUnless(shutil.which('vault') and shutil.which('terraform'), 'Vault/Terraform required')
class AdminLive(unittest.TestCase):
    def test_actual_plan_apply_import_idempotence_and_credentials(self):
        with tempfile.TemporaryDirectory(prefix='admin-tests-') as tmp:
            base = Path(tmp)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            token = uuid.uuid4().hex
            cfg = {'vault_addr': f'http://127.0.0.1:{port}', 'credential_delivery_mount': 'automation-delivery', 'credential_delivery_path': 'restart/credentials'}
            with open(base/'server.log','w') as log:
                process = subprocess.Popen(['vault','server','-dev','-dev-no-store-token',f'-dev-root-token-id={token}',f'-dev-listen-address=127.0.0.1:{port}'], stdout=log, stderr=log)
            try:
                for _ in range(100):
                    try: common.api(cfg,token,'GET','sys/health'); break
                    except Exception: time.sleep(.1)
                # Pre-existing mount and app represent migration from the original script.
                common.api(cfg,token,'POST','sys/auth/approle',{'type':'approle'})
                common.api(cfg,token,'PUT','sys/policies/acl/webapp',{'policy':'path "secret/data/webapp/*" { capabilities=["read"] }'})
                common.api(cfg,token,'POST','auth/approle/role/webapp',{'token_policies':['webapp']})
                synthetic = 'synthetic-' + uuid.uuid4().hex
                common.api(cfg,token,'POST','secret/data/webapp/config',{'data':{'api-key':synthetic,'db-password':synthetic}})
                variables = {'setup_mode':'both','applications':{name:{'fields':['api-key','db-password'],'settings':request.DEFAULT} for name in ['webapp','database']},'restart_settings':json.loads((BASE/'configuration/admin-catalog.json').read_text())['restart_settings']}
                root=base/'plan'; root.mkdir()
                text=(BASE/'configuration/admin-setup/main.tf').read_text().replace('backend "s3" {}','backend "local" {}')
                (root/'main.tf').write_text(text)
                shutil.copy(BASE/'configuration/admin-setup/.terraform.lock.hcl',root/'.terraform.lock.hcl')
                backend=base/'backend.hcl'; backend.write_text(f'path = "{base}/state.tfstate"\n')
                # Exercise the exact scoped policy templates, rather than a root Terraform identity.
                scoped = {}
                for kind in ('plan','deploy'):
                    policy=(BASE/f'bootstrap/admin-{kind}-policy.hcl').read_text()
                    shared='\n'.join(line for line in policy.splitlines() if 'APP_NAME' not in line)
                    specific='\n'.join(line.replace('APP_NAME',name) for name in ('webapp','database','restart') for line in policy.splitlines() if 'APP_NAME' in line)
                    common.api(cfg,token,'PUT',f'sys/policies/acl/admin-{kind}',{'policy':shared+'\n'+specific})
                    scoped[kind]=common.api(cfg,token,'POST','auth/token/create',{'policies':[f'admin-{kind}'],'no_default_policy':True,'ttl':'10m'})['auth']['client_token']
                env=os.environ | {'VAULT_ADDR':cfg['vault_addr'],'VAULT_TOKEN':scoped['plan']}
                output=io.StringIO()
                with contextlib.redirect_stdout(output):
                    changes=pipeline.plan(root,env,cfg,scoped['plan'],variables,backend)
                self.assertTrue(any('create' in x['actions'] for x in changes))
                # Restore the artifact to a different directory, as Actions' apply job does.
                restored=base/'apply'; shutil.copytree(root,restored,ignore=shutil.ignore_patterns('.terraform'))
                pipeline.run_tf(restored,env,'init','-input=false',f'-backend-config={backend}')
                pipeline.run_tf(restored,env | {'VAULT_TOKEN':scoped['deploy']},'apply','-input=false','approved.tfplan')
                with contextlib.redirect_stdout(output):
                    changes=pipeline.plan(restored,env,cfg,scoped['plan'],variables,backend)
                self.assertTrue(all(x['actions']==['no-op'] for x in changes))
                self.assertEqual(common.api(cfg,token,'GET','secret/data/webapp/config')['data']['data']['api-key'],synthetic)
                self.assertEqual(common.api(cfg,token,'GET','auth/approle/role/webapp')['data']['token_ttl'],18000)
                self.assertEqual(common.api(cfg,token,'GET','secret/subkeys/webapp/config')['data']['subkeys'],{'api-key':None,'db-password':None})
                for text in ((base/'state.tfstate').read_text(),output.getvalue()):
                    self.assertNotIn(synthetic,text); self.assertNotIn(token,text)
                # Provisioning did not generate any restart SecretID.
                with self.assertRaises(common.ApiError) as absent:
                    common.api(cfg,token,'LIST','auth/approle/role/restart/secret-id')
                self.assertEqual(absent.exception.status,404)
                common.api(cfg,token,'POST','sys/mounts/automation-delivery',{'type':'kv','options':{'version':'2'}})
                common.api(cfg,token,'PUT','sys/policies/acl/credential-issuer',{'policy':(BASE/'bootstrap/restart-credential-policy.hcl').read_text()})
                issuer=common.api(cfg,token,'POST','auth/token/create',{'policies':['credential-issuer'],'no_default_policy':True,'ttl':'10m'})['auth']['client_token']
                self.assertEqual(credentials.issue(cfg,issuer,0),1)
                for identity in (scoped['plan'],scoped['deploy'],issuer):
                    with self.assertRaises(common.ApiError) as denied:
                        common.api(cfg,identity,'GET','secret/data/webapp/config')
                    self.assertEqual(denied.exception.status,403)
                with self.assertRaises(common.ApiError) as denied:
                    common.api(cfg,issuer,'GET','automation-delivery/data/restart/credentials')
                self.assertEqual(denied.exception.status,403)
                with self.assertRaises(ValueError): credentials.issue(cfg,issuer,0)
                self.assertEqual(common.api(cfg,token,'GET','automation-delivery/metadata/restart/credentials')['data']['current_version'],1)
                before=common.api(cfg,token,'LIST','auth/approle/role/restart/secret-id')['data']['keys']
                def failed_delivery(c,t,method,path,payload=None,query=None):
                    if method == 'POST' and path == 'automation-delivery/data/restart/credentials':
                        raise common.ApiError(403,path)
                    return common.api(c,t,method,path,payload,query)
                with patch.object(credentials,'api',failed_delivery), self.assertRaisesRegex(RuntimeError,'generated SecretID revoked'):
                    credentials.issue(cfg,issuer,1)
                self.assertEqual(common.api(cfg,token,'LIST','auth/approle/role/restart/secret-id')['data']['keys'],before)
                # A reduced desired set may never delete managed apps.
                variables['applications'].pop('database')
                with contextlib.redirect_stdout(output), self.assertRaises(ValueError):
                    pipeline.plan(restored,env,cfg,scoped['plan'],variables,backend)
            finally:
                process.terminate(); process.wait(timeout=10)

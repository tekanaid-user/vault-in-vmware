"""Shared configuration, Git revision, HTTPS and authentication helpers.

Imported by Section 13 scripts; this module is not a command-line entry point.
Settings come from environments/<env>/settings.json, not VAULT_ADDR overrides.
Live addresses must be HTTPS; VAULT_CACERT optionally supplies a trusted CA PEM.
Actions authentication exchanges a GitHub JWT for the configured role's Vault
token; outside Actions the caller's VAULT_TOKEN or ~/.vault-token is reused.
Only tokens created by this helper are revoked. API errors suppress response
bodies; callers must never print returned credentials. See SCRIPT-REFERENCE.md."""
import json
import os
import re
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
REPO = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=BASE, text=True).strip())
PREFIX = BASE.relative_to(REPO).as_posix()

class ApiError(RuntimeError):
    """Carry HTTP status/path for findings without retaining a server response body."""
    def __init__(self, status, path):
        self.status = status
        super().__init__(f'Vault HTTP {status} at {path}; response body suppressed')

def settings(env, live=True, filename=None):
    """Load environment settings or an explicit file; require HTTPS/no namespaces.

    filename is used by the local lab CLI without editing committed definitions.
    """
    result = json.loads((Path(filename) if filename else BASE / 'environments' / env / 'settings.json').read_text())
    if result.get('namespace'):
        raise ValueError('Vault Community Edition has no namespaces; remove namespace configuration')
    if live and ('CHANGE_ME' in result['vault_addr'] or not result['vault_addr'].startswith('https://')):
        raise ValueError('Configure an HTTPS Vault address before live operations')
    return result

def revision(env, explicit=None):
    """Resolve the original reporting release to an existing full Git commit SHA."""
    line = (BASE / 'environments' / env / 'release.yaml').read_text().strip()
    match = re.fullmatch(r'configuration_ref:\s*([0-9a-f]{40})', line)
    sha = explicit or (match.group(1) if match else '')
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Use a full reviewed commit SHA; configure release.yaml first')
    resolved = subprocess.check_output(['git', 'rev-parse', f'{sha}^{{commit}}'], cwd=REPO, text=True).strip()
    if resolved != sha:
        raise ValueError('Configuration reference must identify a commit')
    return sha

def read_revision(sha, filename):
    """Return a configuration file at the pinned SHA without changing the checkout."""
    return subprocess.check_output(['git', 'show', f'{sha}:{PREFIX}/configuration/{filename}'], cwd=REPO)

def app_definition(sha=None):
    """Load and validate the original single-app baseline, including unique field names."""
    raw = read_revision(sha, 'application.json') if sha else (BASE / 'configuration/application.json').read_bytes()
    app = json.loads(raw)
    for key in ('kv_mount', 'secret_path', 'application', 'policy_name', 'approle_name'):
        if not re.fullmatch(r'[a-zA-Z0-9_/-]+', app[key]) or '..' in app[key]:
            raise ValueError(f'Invalid application definition: {key}')
    if not app['fields'] or len(set(app['fields'])) != len(app['fields']):
        raise ValueError('Expected fields must be non-empty and unique')
    return app

def api(cfg, token, method, path, payload=None, query=None):
    """Send a 30-second HTTPS JSON request; raise safe errors without response bodies.

    Paths are URL-escaped while retaining separators. Return decoded JSON (or {}).
    VAULT_CACERT controls trust; callers decide which methods/paths are permissible."""
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {'X-Vault-Token': token, 'Content-Type': 'application/json'}
    if cfg.get('namespace'):
        raise ValueError('Vault Community Edition does not support namespaces')
    context = ssl.create_default_context(cafile=os.environ.get('VAULT_CACERT'))
    url = cfg['vault_addr'].rstrip('/') + '/v1/' + urllib.parse.quote(path, safe='/')
    if query:
        url += '?' + urllib.parse.urlencode(query)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method=method), context=context, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        raise ApiError(status, path) from None
    except urllib.error.URLError:
        raise RuntimeError('Vault connection/TLS failure; details suppressed') from None

def github_jwt(audience):
    """Request the configured audience from Actions; keep the bearer JWT in memory."""
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('Run this step in GitHub Actions with id-token: write')
    try:
        url = os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']
        separator = '&' if '?' in url else '?'
        url += separator + urllib.parse.urlencode({'audience': audience})
        request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)['value']
    except Exception:
        raise RuntimeError('GitHub OIDC request failed; response suppressed') from None

def authenticate(cfg, role_kind='deploy'):
    """Return (token, owned); owned=True only for a newly exchanged Actions identity.

    role_kind selects settings[<kind>_role]. Local fallback tokens belong to the
    operator and must not be revoked by close_token()."""
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        jwt = github_jwt(cfg['oidc_audience'])
        result = api(cfg, '', 'POST', f"auth/{cfg['jwt_auth_path']}/login", {'role': cfg[f'{role_kind}_role'], 'jwt': jwt})
        return result['auth']['client_token'], True
    token = os.environ.get('VAULT_TOKEN')
    if not token:
        path = Path.home() / '.vault-token'
        token = path.read_text().strip() if path.exists() else None
    if not token:
        raise ValueError('Authenticate locally with Vault CLI or VAULT_TOKEN first')
    return token, False

def close_token(cfg, token, owned):
    """Best-effort revoke-self for owned tokens; short TTL remains the failure fallback."""
    if owned:
        try:
            api(cfg, token, 'POST', 'auth/token/revoke-self', {})
        except Exception:
            pass  # Short TTL remains the fallback; never print credentials.

def current_version(cfg, token, app):
    """Read KV v2 metadata version; 404 means 0, other failures remain errors."""
    try:
        data = api(cfg, token, 'GET', f"{app['kv_mount']}/metadata/{app['secret_path']}")['data']
        return data['current_version']
    except ApiError as error:
        if error.status == 404:
            return 0
        raise

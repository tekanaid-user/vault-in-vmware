# Read-only inventory. Review/extend exact supported plugin endpoints before use.
# No sudo, root token, KV data, login, issuance, exports or credential endpoints.
path "sys/auth" { capabilities = ["read"] }
path "sys/mounts" { capabilities = ["read"] }
path "sys/mounts/auth/+/tune" { capabilities = ["read"] }
path "sys/mounts/+/tune" { capabilities = ["read"] }
path "sys/policies/acl" { capabilities = ["list"] }
path "sys/policies/acl/*" { capabilities = ["read"] }
path "sys/policies/password" { capabilities = ["list"] }
path "sys/policies/password/+" { capabilities = ["read"] }
path "sys/capabilities-self" { capabilities = ["update"] } # read-only capability introspection
path "auth/token/revoke-self" { capabilities = ["update"] }

# Every KV v2 mount: metadata and subkeys only. No */data/* grants.
# + matches a single path segment. Add exact rules for nested mount names.
path "+/metadata" { capabilities = ["list"] }
path "+/metadata/*" { capabilities = ["read", "list"] }
path "+/subkeys/*" { capabilities = ["read"] }
path "+/config" { capabilities = ["read"] }

# Config GETs return documented configuration, not KV values. Collector exports
# allowlisted fingerprints only. No credential-generating or RoleID/SecretID reads.
path "auth/+/config" { capabilities = ["read"] }
path "auth/+/role" { capabilities = ["list"] }
path "auth/+/role/+" { capabilities = ["read"] }
path "auth/+/roles" { capabilities = ["list"] }
path "auth/+/roles/*" { capabilities = ["read", "list"] }
path "auth/+/groups" { capabilities = ["list"] }
path "auth/+/groups/*" { capabilities = ["read", "list"] }
path "auth/+/users" { capabilities = ["list"] }
path "auth/+/users/*" { capabilities = ["read", "list"] }
path "auth/+/map/teams" { capabilities = ["list"] }
path "auth/+/map/teams/*" { capabilities = ["read", "list"] }
path "auth/+/map/users" { capabilities = ["list"] }
path "auth/+/map/users/*" { capabilities = ["read", "list"] }
path "+/keys" { capabilities = ["list"] }
path "+/keys/*" { capabilities = ["read", "list"] }
path "+/roles" { capabilities = ["list"] }
path "+/roles/*" { capabilities = ["read", "list"] }
path "+/static-roles" { capabilities = ["list"] }
path "+/static-roles/*" { capabilities = ["read", "list"] }
path "+/config/urls" { capabilities = ["read"] }
path "+/config/crl" { capabilities = ["read"] }

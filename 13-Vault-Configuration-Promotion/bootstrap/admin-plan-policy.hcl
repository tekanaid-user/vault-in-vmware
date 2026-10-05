# Replace application placeholders with each approved catalog name.
# Add restart equivalents only if managed. No application values/SecretID reads.
path "sys/auth" { capabilities = ["read"] }
path "sys/mounts" { capabilities = ["read"] }
path "sys/auth/approle/tune" { capabilities = ["read"] }
path "sys/mounts/secret/tune" { capabilities = ["read"] }
path "sys/policies/acl/APP_NAME" { capabilities = ["read"] }
path "auth/approle/role/APP_NAME" { capabilities = ["read"] }
path "auth/approle/role/APP_NAME/role-id" { capabilities = ["read"] }
path "auth/token/lookup-self" { capabilities = ["read"] }
path "auth/token/revoke-self" { capabilities = ["update"] }

path "sys/mounts/auth/approle" { capabilities = ["read"] }
path "sys/mounts/secret" { capabilities = ["read"] }

path "sys/mounts/auth/approle/tune" { capabilities = ["read"] }

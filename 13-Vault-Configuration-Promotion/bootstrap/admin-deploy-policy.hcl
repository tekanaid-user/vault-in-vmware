# Replace APP_NAME with each approved catalog name; add restart if managed.
# Mount creation requires sudo; there are no delete capabilities.
path "sys/auth" { capabilities = ["read"] }
path "sys/mounts" { capabilities = ["read"] }
path "sys/auth/approle" { capabilities = ["create", "update", "read", "sudo"] }
path "sys/auth/approle/tune" { capabilities = ["read", "update", "sudo"] }
path "sys/mounts/secret" { capabilities = ["create", "update", "read", "sudo"] }
path "sys/mounts/secret/tune" { capabilities = ["read", "update", "sudo"] }
path "sys/policies/acl/APP_NAME" { capabilities = ["read", "create", "update"] }
path "auth/approle/role/APP_NAME" { capabilities = ["read", "create", "update"] }
path "auth/approle/role/APP_NAME/role-id" { capabilities = ["read"] }
path "auth/token/lookup-self" { capabilities = ["read"] }
path "auth/token/revoke-self" { capabilities = ["update"] }

path "sys/mounts/auth/approle" { capabilities = ["read"] }

path "sys/mounts/auth/approle/tune" { capabilities = ["read"] }

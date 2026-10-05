# Delivery mount and reader policies must be created separately by the Vault admin.
path "sys/mounts" { capabilities = ["read"] }
path "auth/approle/role/restart/role-id" { capabilities = ["read"] }
path "auth/approle/role/restart/secret-id" { capabilities = ["update"] }
path "auth/approle/role/restart/secret-id-accessor/destroy" { capabilities = ["update"] }
path "automation-delivery/metadata/restart/credentials" { capabilities = ["read"] }
path "automation-delivery/data/restart/credentials" { capabilities = ["create", "update"] }
path "auth/token/lookup-self" { capabilities = ["read"] }
path "auth/token/revoke-self" { capabilities = ["update"] }

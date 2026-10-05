# Default deploy identity: changes policy/AppRole only; reads structure, never values.
path "sys/policies/acl/demo-app" {
  capabilities = ["read", "create", "update"]
}
path "auth/approle/role/demo-app" {
  capabilities = ["read", "create", "update"]
}
path "secret/metadata/demo/app" {
  capabilities = ["read"]
}
path "secret/subkeys/demo/app" {
  capabilities = ["read"]
}
path "auth/token/revoke-self" {
  capabilities = ["update"]
}
# This policy does not allow target secret reads or destruction of the target.

# Terraform reads the non-secret RoleID while refreshing the AppRole.
path "auth/approle/role/demo-app/role-id" {
  capabilities = ["read"]
}

# Terraform validates its own token; no default policy is attached by OIDC.
path "auth/token/lookup-self" {
  capabilities = ["read"]
}

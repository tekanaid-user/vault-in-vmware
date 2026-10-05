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

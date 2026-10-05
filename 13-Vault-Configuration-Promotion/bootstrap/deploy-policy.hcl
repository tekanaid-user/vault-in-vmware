# Default deploy identity: changes policy/AppRole only; reads structure, never values.
path "sys/policies/acl/demo-demo-dbit" {
  capabilities = ["read", "create", "update"]
}
path "auth/approle/role/demo-demo-dbit" {
  capabilities = ["read", "create", "update"]
}
path "secret/metadata/demo-demo/dbit" {
  capabilities = ["read"]
}
path "secret/subkeys/demo-demo/dbit" {
  capabilities = ["read"]
}
path "auth/token/revoke-self" {
  capabilities = ["update"]
}
# This policy does not allow target secret reads or destruction of the target.

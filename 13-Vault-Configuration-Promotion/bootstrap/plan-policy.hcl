# Default plan identity: reads configuration/structure only; no secret-data access.
path "sys/policies/acl/demo-demo-dbit" {
  capabilities = ["read"]
}
path "auth/approle/role/demo-demo-dbit" {
  capabilities = ["read"]
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

# Default plan identity: reads configuration/structure only; no secret-data access.
path "sys/policies/acl/opers-demo-dbit" {
  capabilities = ["read"]
}
path "auth/approle/role/opers-demo-dbit" {
  capabilities = ["read"]
}
path "secret/metadata/opers-demo/dbit" {
  capabilities = ["read"]
}
path "secret/subkeys/opers-demo/dbit" {
  capabilities = ["read"]
}
path "auth/token/revoke-self" {
  capabilities = ["update"]
}
# This policy does not allow target secret reads or destruction of the target.

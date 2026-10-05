# Example only: narrow scope to the approved application prefix.
path "secret/metadata/opers-demo" {
  capabilities = ["list"]
}
path "secret/metadata/opers-demo/*" {
  capabilities = ["read", "list"]
}
path "secret/subkeys/opers-demo/*" {
  capabilities = ["read"]
}
path "sys/policies/acl/opers-demo-dbit" {
  capabilities = ["read"]
}
path "auth/token/revoke-self" {
  capabilities = ["update"]
}
# Deliberately no secret/data capability.

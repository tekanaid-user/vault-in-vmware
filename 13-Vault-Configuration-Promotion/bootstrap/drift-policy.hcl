# Example only: narrow scope to the approved application prefix.
path "secret/metadata/demo-demo" {
  capabilities = ["list"]
}
path "secret/metadata/demo-demo/*" {
  capabilities = ["read", "list"]
}
path "secret/subkeys/demo-demo/*" {
  capabilities = ["read"]
}
path "sys/policies/acl/demo-demo-dbit" {
  capabilities = ["read"]
}
path "auth/token/revoke-self" {
  capabilities = ["update"]
}
# Deliberately no secret/data capability.

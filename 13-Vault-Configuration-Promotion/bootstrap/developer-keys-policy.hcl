# Keys-only API/CLI access. Do not combine with policies granting data read.
path "secret/metadata/demo" {
  capabilities = ["list"]
}
path "secret/metadata/demo/*" {
  capabilities = ["list"]
}
path "secret/subkeys/demo/*" {
  capabilities = ["read"]
}

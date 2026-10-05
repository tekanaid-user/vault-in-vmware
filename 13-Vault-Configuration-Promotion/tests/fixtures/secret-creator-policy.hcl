# Named Security identity: initial creation only. CAS=0 in the guided writer
# adds protection against overwrite even if the identity has other permissions.
path "secret/data/demo/app" {
  capabilities = ["create"]
}
path "secret/subkeys/demo/app" {
  capabilities = ["read"]
}

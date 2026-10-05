# Example S3 backend; replace with approved storage before use.
# Credentials come from the runner's identity, not this file or GitHub secrets.
bucket       = "CHANGE_ME_APPROVED_STATE_BUCKET"
key          = "vault-demo/uat/configuration.tfstate"
region       = "us-east-1"
encrypt      = true
use_lockfile = true

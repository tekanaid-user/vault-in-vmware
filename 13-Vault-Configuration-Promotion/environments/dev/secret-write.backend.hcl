# Example S3 backend; replace with OPERS-approved storage before use.
# Credentials come from the runner's identity, not this file or GitHub secrets.
bucket       = "CHANGE_ME_APPROVED_STATE_BUCKET"
key          = "opers-vault/dev/secret-write.tfstate"
region       = "us-east-1"
encrypt      = true
use_lockfile = true

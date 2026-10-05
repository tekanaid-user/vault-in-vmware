terraform {
  required_version = ">= 1.11.0, < 2.0.0"
  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = "= 5.8.0"
    }
  }
  backend "s3" {}
}

# VAULT_ADDR and a short-lived VAULT_TOKEN are provided by the GitHub Actions pipeline helper.
provider "vault" {
  skip_child_token = true
}

variable "token_bound_cidrs" {
  type = list(string)
}

locals {
  app = jsondecode(file("${path.module}/../application.json"))
}

resource "vault_policy" "application" {
  name = local.app.policy_name
  policy = templatefile("${path.module}/../policy.hcl.tftpl", {
    kv_mount    = local.app.kv_mount
    secret_path = local.app.secret_path
  })
}

# AppRole auth is assumed to exist already. No RoleIDs/SecretIDs are generated.
resource "vault_approle_auth_backend_role" "application" {
  backend            = "approle"
  role_name          = local.app.approle_name
  token_policies     = [vault_policy.application.name]
  token_ttl          = 3600
  token_max_ttl      = 14400
  secret_id_ttl      = 86400
  secret_id_num_uses = 1
  token_bound_cidrs  = var.token_bound_cidrs
  lifecycle {
    prevent_destroy = true
  }
}

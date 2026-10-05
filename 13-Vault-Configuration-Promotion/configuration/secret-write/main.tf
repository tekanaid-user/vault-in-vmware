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

provider "vault" {
  skip_child_token = true
}

variable "request_id" {
  type = string
}
variable "staging_mount" {
  type = string
}
variable "expected_version" {
  type = number
}
variable "write_version" {
  type = number
}

locals {
  app = jsondecode(file("${path.module}/../application.json"))
}

# Only an ephemeral reader sees values. The ordinary KV data source is not used.
ephemeral "vault_kv_secret_v2" "staged" {
  mount   = var.staging_mount
  name    = "${local.app.application}/${var.request_id}"
  version = 1
}

resource "vault_kv_secret_v2" "application" {
  mount                = local.app.kv_mount
  name                 = local.app.secret_path
  data_json_wo         = ephemeral.vault_kv_secret_v2.staged.data_json
  data_json_wo_version = var.write_version
  cas                  = var.expected_version
  disable_read         = true
  delete_all_versions  = false
  lifecycle {
    prevent_destroy = true
  }
}

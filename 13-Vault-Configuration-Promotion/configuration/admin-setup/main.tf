terraform {
  required_version = ">= 1.11.0"
  backend "s3" {}
  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = "5.8.0"
    }
  }
}
provider "vault" {
  skip_child_token = true
}
variable "setup_mode" {
  type = string
  validation {
    condition     = contains(["applications", "restart", "both"], var.setup_mode)
    error_message = "Select applications, restart or both."
  }
}
variable "applications" {
  type = map(object({
    fields = list(string)
    settings = object({
      secret_id_ttl           = number
      secret_id_num_uses      = number
      token_ttl               = number
      token_max_ttl           = number
      token_num_uses          = number
      token_bound_cidrs       = list(string)
      secret_id_bound_cidrs   = list(string)
      token_no_default_policy = bool
    })
  }))
}
variable "restart_settings" {
  type = object({
    secret_id_ttl           = number
    secret_id_num_uses      = number
    token_ttl               = number
    token_max_ttl           = number
    token_num_uses          = number
    token_bound_cidrs       = list(string)
    secret_id_bound_cidrs   = list(string)
    token_no_default_policy = bool
  })
}
locals {
  manage_applications = contains(["applications", "both"], var.setup_mode)
  manage_restart      = contains(["restart", "both"], var.setup_mode)
}
resource "vault_auth_backend" "approle" {
  type = "approle"
  path = "approle"
}
resource "vault_mount" "secret" {
  count = local.manage_applications ? 1 : 0
  path  = "secret"
  type  = "kv"
  options = {
    version = "2"
  }
}
resource "vault_policy" "application" {
  for_each = local.manage_applications ? var.applications : {}
  name     = each.key
  policy = jsonencode({
    path = {
      "secret/data/${each.key}/*"     = { capabilities = ["read", "list"] }
      "secret/metadata/${each.key}"   = { capabilities = ["list"] }
      "secret/metadata/${each.key}/*" = { capabilities = ["list"] }
    }
  })
}
resource "vault_approle_auth_backend_role" "application" {
  for_each                = local.manage_applications ? var.applications : {}
  backend                 = vault_auth_backend.approle.path
  role_name               = each.key
  token_policies          = [vault_policy.application[each.key].name]
  secret_id_ttl           = each.value.settings.secret_id_ttl
  secret_id_num_uses      = each.value.settings.secret_id_num_uses
  token_ttl               = each.value.settings.token_ttl
  token_max_ttl           = each.value.settings.token_max_ttl
  token_num_uses          = each.value.settings.token_num_uses
  token_bound_cidrs       = each.value.settings.token_bound_cidrs
  secret_id_bound_cidrs   = each.value.settings.secret_id_bound_cidrs
  token_no_default_policy = each.value.settings.token_no_default_policy
}
resource "vault_policy" "restart" {
  count = local.manage_restart ? 1 : 0
  name  = "restart"
  policy = jsonencode({
    path = merge(
      { for name in keys(var.applications) : "auth/approle/role/${name}/secret-id" => {
        capabilities     = ["create", "update"]
        min_wrapping_ttl = "100s"
        max_wrapping_ttl = "300s"
      } },
      { for name in keys(var.applications) : "auth/approle/role/${name}/role-id" => {
        capabilities = ["read"]
      } }
    )
  })
}
resource "vault_approle_auth_backend_role" "restart" {
  count                   = local.manage_restart ? 1 : 0
  backend                 = vault_auth_backend.approle.path
  role_name               = "restart"
  token_policies          = [vault_policy.restart[0].name]
  secret_id_ttl           = var.restart_settings.secret_id_ttl
  secret_id_num_uses      = var.restart_settings.secret_id_num_uses
  token_ttl               = var.restart_settings.token_ttl
  token_max_ttl           = var.restart_settings.token_max_ttl
  token_num_uses          = var.restart_settings.token_num_uses
  token_bound_cidrs       = var.restart_settings.token_bound_cidrs
  secret_id_bound_cidrs   = var.restart_settings.secret_id_bound_cidrs
  token_no_default_policy = var.restart_settings.token_no_default_policy
}

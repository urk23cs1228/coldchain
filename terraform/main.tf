# ColdChain AI — Terraform Infrastructure as Code
# Phase 3: Provisions Resource Group, ACR, and AKS on Azure
# Usage: terraform init && terraform plan && terraform apply

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80"
    }
  }
  required_version = ">= 1.5.0"
}

provider "azurerm" {
  features {}
  # Credentials from environment variables:
  # ARM_CLIENT_ID, ARM_CLIENT_SECRET, ARM_SUBSCRIPTION_ID, ARM_TENANT_ID
}

# ── Variables ─────────────────────────────────────────────────
variable "resource_group_name" {
  default = "coldchain-rg"
}
variable "location" {
  default = "East US"
}
variable "acr_name" {
  # Must be globally unique, alphanumeric only, 5–50 chars
  default = "coldchainacr"
}
variable "aks_cluster_name" {
  default = "coldchain-aks"
}
variable "node_count" {
  default = 2
}
variable "node_vm_size" {
  default = "Standard_B2s"   # 2 vCPU, 4 GB RAM — cost-effective
}

# ── Resource Group ────────────────────────────────────────────
resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
  tags = {
    project = "ColdChain AI"
    env     = "production"
  }
}

# ── Azure Container Registry (ACR) ───────────────────────────
resource "azurerm_container_registry" "acr" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
  admin_enabled       = true

  tags = {
    project = "ColdChain AI"
  }
}

# ── Azure Kubernetes Service (AKS) ────────────────────────────
resource "azurerm_kubernetes_cluster" "aks" {
  name                = var.aks_cluster_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  dns_prefix          = "coldchain"

  default_node_pool {
    name       = "default"
    node_count = var.node_count
    vm_size    = var.node_vm_size
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin = "kubenet"
    load_balancer_sku = "standard"
  }

  tags = {
    project = "ColdChain AI"
  }
}

# ── Grant AKS pull access to ACR ─────────────────────────────
resource "azurerm_role_assignment" "aks_acr_pull" {
  principal_id                     = azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id
  role_definition_name             = "AcrPull"
  scope                            = azurerm_container_registry.acr.id
  skip_service_principal_aad_check = true
}

# ── Outputs ───────────────────────────────────────────────────
output "resource_group_name" {
  value = azurerm_resource_group.rg.name
}
output "acr_login_server" {
  value = azurerm_container_registry.acr.login_server
}
output "aks_cluster_name" {
  value = azurerm_kubernetes_cluster.aks.name
}
output "aks_kube_config" {
  value     = azurerm_kubernetes_cluster.aks.kube_config_raw
  sensitive = true
}

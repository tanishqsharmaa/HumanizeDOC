@description('Storage account name (must be globally unique, 3-24 lowercase alphanumeric)')
param storageAccountName string = 'humanizedocstorage'

@description('Azure region for all resources')
param location string = resourceGroup().location

// ── Storage Account (Standard_LRS, StorageV2) ────────────────────
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

// ── Blob Service ─────────────────────────────────────────────────
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

// ── Blob Container: humanizedoc-uploads (private access) ─────────
resource uploadsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'humanizedoc-uploads'
  properties: {
    publicAccess: 'None'
  }
}

// ── Lifecycle Management Policy: delete blobs after 1 day ────────
resource managementPolicy 'Microsoft.Storage/storageAccounts/managementPolicies@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'delete-after-one-day'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['humanizedoc-uploads/']
            }
            actions: {
              baseBlob: {
                delete: {
                  daysAfterModificationGreaterThan: 1
                }
              }
            }
          }
        }
      ]
    }
  }
}

// ── Outputs ───────────────────────────────────────────────────────
output storageAccountName string = storageAccount.name
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob

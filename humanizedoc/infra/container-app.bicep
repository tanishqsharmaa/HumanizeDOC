@description('Name of the Container App')
param containerAppName string

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Full ACR image path, e.g. humanizedocregistry.azurecr.io/humanizedoc-backend:latest')
param containerImage string

@description('Groq API key')
@secure()
param groqApiKey string

@description('Google Gemini API key')
@secure()
param geminiApiKey string

@description('Azure Blob Storage connection string')
@secure()
param azureStorageConnectionString string

@description('Azure Blob container name for uploads')
param blobContainerName string = 'humanizedoc-uploads'

// ── Container Apps Environment (Consumption workload profile) ──────
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: '${containerAppName}-env'
  location: location
  properties: {
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// ── Container App ─────────────────────────────────────────────────
resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: containerAppName
  location: location
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        allowInsecure: false
        transport: 'http'
      }
      secrets: [
        {
          name: 'groq-api-key'
          value: groqApiKey
        }
        {
          name: 'gemini-api-key'
          value: geminiApiKey
        }
        {
          name: 'azure-storage-connection-string'
          value: azureStorageConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'humanizedoc-backend'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'GROQ_API_KEY'
              secretRef: 'groq-api-key'
            }
            {
              name: 'GEMINI_API_KEY'
              secretRef: 'gemini-api-key'
            }
            {
              name: 'AZURE_STORAGE_CONNECTION_STRING'
              secretRef: 'azure-storage-connection-string'
            }
            {
              name: 'AZURE_BLOB_CONTAINER_NAME'
              value: blobContainerName
            }
            {
              name: 'HUMANIZER_BACKEND'
              value: 'groq'
            }
            {
              name: 'MAX_FILE_SIZE_MB'
              value: '15'
            }
            {
              name: 'MAX_WORDS_PER_REQUEST'
              value: '12000'
            }
            {
              name: 'CHUNK_SIZE_WORDS'
              value: '500'
            }
            {
              name: 'FILE_EXPIRY_MINUTES'
              value: '60'
            }
            {
              name: 'RATE_LIMIT_PER_IP_PER_DAY'
              value: '5'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 5
        rules: [
          {
            name: 'http-scale-rule'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}

// ── Outputs ───────────────────────────────────────────────────────
output containerAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'

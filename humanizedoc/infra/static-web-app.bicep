@description('Name of the Static Web App')
param appName string

@description('Azure region for the Static Web App')
param location string

@description('Container App URL (backend API base URL)')
param backendApiUrl string

// ── Static Web App (Free SKU, Next.js) ───────────────────────────
// Note: repositoryUrl and branch are intentionally omitted here.
// Deployments are handled by the GitHub Actions workflow using the
// Azure Static Web Apps deploy action and AZURE_STATIC_WEB_APPS_API_TOKEN.
resource staticWebApp 'Microsoft.Web/staticSites@2022-09-01' = {
  name: appName
  location: location
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    buildProperties: {
      appLocation: '/frontend'
      outputLocation: '.next'
    }
  }
}

// ── App settings: inject backend API URL ─────────────────────────
resource staticWebAppSettings 'Microsoft.Web/staticSites/config@2022-09-01' = {
  parent: staticWebApp
  name: 'appsettings'
  properties: {
    NEXT_PUBLIC_API_URL: backendApiUrl
  }
}

// ── Outputs ───────────────────────────────────────────────────────
output staticWebAppUrl string = 'https://${staticWebApp.properties.defaultHostname}'

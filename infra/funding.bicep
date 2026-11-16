targetScope = 'resourceGroup'

param location string = resourceGroup().location
param tenantId string
param apiContainerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
param fabricWorkspaceId string
param fabricLakehouseId string
param fabricSqlServer string
param fabricSqlDatabase string
param fabricCapacityResourceGroup string
param fabricCapacityName string
param webClientId string
param apiAudience string
param webApiScope string
param enableFundingIntelligence bool = false
param fundingModelName string = 'gpt-5.6-luna'
param fundingModelVersion string = '2026-07-09'
param fundingSearchLocation string = location
param enableFundingWork bool = false
param workIqClientId string = ''
param workIqKeyVaultUri string = ''
param workIqClientCertificateSecretName string = ''
param workIqFundingDocumentUrls string = ''
param workIqFundingDocumentIdentities string = ''

var suffix = uniqueString(resourceGroup().id)
var tags = {
  project: 'award-iq'
  scenario: 'funding-readiness'
}
var identityName = 'id-award-iq'

module identity 'modules/identity.bicep' = {
  name: 'award-iq-identity'
  params: {
    location: location
    managedIdentityName: identityName
    tags: tags
  }
}

module observability 'modules/observability.bicep' = {
  name: 'award-iq-observability'
  params: {
    location: location
    logAnalyticsName: 'log-award-iq'
    appInsightsName: 'appi-award-iq'
    tags: tags
  }
}

module knowledge 'modules/funding-knowledge.bicep' = if (enableFundingIntelligence) {
  name: 'award-iq-knowledge'
  params: {
    location: location
    accountName: 'award-iq-ai-${suffix}'
    searchName: 'award-iq-search-${suffix}-${fundingSearchLocation}'
    searchLocation: fundingSearchLocation
    principalId: identity.outputs.principalId
    modelName: fundingModelName
    modelVersion: fundingModelVersion
    tags: tags
  }
}

module apps 'modules/apps.bicep' = {
  name: 'award-iq-apps'
  params: {
    location: location
    containerAppsEnvironmentName: 'cae-award-iq'
    apiContainerAppName: 'ca-award-iq-api'
    apiContainerImage: apiContainerImage
    apiContainerPort: 8000
    staticWebAppName: 'swa-award-iq-${suffix}'
    containerRegistryName: 'awardiq${suffix}acr'
    logAnalyticsCustomerId: observability.outputs.logAnalyticsCustomerId
    logAnalyticsSharedKey: observability.outputs.logAnalyticsSharedKey
    appInsightsConnectionString: observability.outputs.appInsightsConnectionString
    identityResourceId: identity.outputs.identityId
    identityPrincipalId: identity.outputs.principalId
    identityClientId: identity.outputs.clientId
    fabricWorkspaceId: fabricWorkspaceId
    fabricLakehouseId: fabricLakehouseId
    fabricSqlServer: fabricSqlServer
    fabricSqlDatabase: fabricSqlDatabase
    azureSubscriptionId: subscription().subscriptionId
    fabricCapacityResourceGroup: fabricCapacityResourceGroup
    fabricCapacityName: fabricCapacityName
    tenantId: tenantId
    apiAudience: apiAudience
    apiRequiredScope: 'access_as_user'
    searchEndpoint: enableFundingIntelligence ? knowledge!.outputs.searchEndpoint : ''
    foundryKbName: enableFundingIntelligence ? 'award-iq-funding-kb' : ''
    foundryKsName: enableFundingIntelligence ? 'award-iq-funding-ks' : ''
    searchApiVersion: '2026-08-01-preview'
    modelEndpoint: enableFundingIntelligence ? knowledge!.outputs.modelEndpoint : ''
    modelDeployment: enableFundingIntelligence ? knowledge!.outputs.modelDeployment : ''
    useLiveFundingLlm: enableFundingIntelligence
    useLiveFoundry: enableFundingIntelligence
    workIqClientId: workIqClientId
    workIqClientCertificateSecretName: workIqClientCertificateSecretName
    workIqEndpoint: 'https://workiq.svc.cloud.microsoft/a2a/'
    workIqScope: 'api://workiq.svc.cloud.microsoft/.default'
    workIqFundingDocumentUrls: workIqFundingDocumentUrls
    workIqFundingDocumentIdentities: workIqFundingDocumentIdentities
    keyVaultUri: workIqKeyVaultUri
    useLiveWork: enableFundingWork
    tags: tags
  }
}

output API_URL string = apps.outputs.apiUrl
output WEB_URL string = apps.outputs.staticWebAppUrl
output API_CONTAINER_APP_NAME string = 'ca-award-iq-api'
output STATIC_WEB_APP_NAME string = 'swa-award-iq-${suffix}'
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = apps.outputs.containerRegistryEndpoint
output AZURE_MANAGED_IDENTITY_NAME string = identityName
output AZURE_MANAGED_IDENTITY_CLIENT_ID string = identity.outputs.clientId
output VITE_API_BASE_URL string = apps.outputs.apiUrl
output VITE_ENTRA_TENANT_ID string = tenantId
output VITE_ENTRA_CLIENT_ID string = webClientId
output VITE_API_SCOPE string = webApiScope
output SEARCH_ENDPOINT string = enableFundingIntelligence ? knowledge!.outputs.searchEndpoint : ''
output FOUNDRY_ENDPOINT string = enableFundingIntelligence ? knowledge!.outputs.modelEndpoint : ''
output MODEL_DEPLOYMENT string = enableFundingIntelligence ? knowledge!.outputs.modelDeployment : ''

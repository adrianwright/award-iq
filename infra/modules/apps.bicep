param location string
param containerAppsEnvironmentName string
param apiContainerAppName string
param apiContainerImage string
param apiContainerPort int
param staticWebAppName string
param containerRegistryName string
param logAnalyticsCustomerId string
@secure()
param logAnalyticsSharedKey string
param appInsightsConnectionString string
param identityResourceId string
param identityPrincipalId string
param identityClientId string
param searchEndpoint string
param foundryKbName string
param fabricWorkspaceId string
param azureSubscriptionId string
param fabricCapacityResourceGroup string
param fabricCapacityName string
param tenantId string
param apiAudience string
param apiRequiredScope string
param workIqClientId string
param workIqClientCertificateSecretName string
param workIqEndpoint string
param workIqScope string
param useLiveWork bool
param keyVaultUri string
param tags object
param fabricLakehouseId string = ''
param fabricSqlServer string = ''
param fabricSqlDatabase string = ''
param useLiveFoundry bool = false
param useLiveFundingLlm bool = false
param foundryKsName string = ''
param searchApiVersion string = '2026-05-01-preview'
param modelEndpoint string = ''
param modelDeployment string = ''
param workIqFundingDocumentUrls string = ''
param workIqFundingDocumentIdentities string = ''

// Azure built-in AcrPull role definition ID: a public Microsoft constant, not an environment ID.
var acrPullRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvironmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: containerRegistryName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, identityPrincipalId, acrPullRoleId)
  scope: containerRegistry
  properties: {
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleId
  }
}

resource web 'Microsoft.Web/staticSites@2023-12-01' = {
  name: staticWebAppName
  location: location
  tags: union(tags, {
    'azd-service-name': 'web'
  })
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    allowConfigFileUpdates: true
    stagingEnvironmentPolicy: 'Enabled'
  }
}

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: apiContainerAppName
  location: location
  tags: union(tags, {
    'azd-service-name': 'api'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceId}': {}
    }
  }
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: apiContainerPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: identityResourceId
        }
      ]
    }
    template: {
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
      containers: [
        {
          name: 'api'
          image: apiContainerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionString
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: identityClientId
            }
            {
              name: 'SEARCH_ENDPOINT'
              value: searchEndpoint
            }
            {
              name: 'FOUNDRY_KB_NAME'
              value: foundryKbName
            }
            {
              name: 'FABRIC_WORKSPACE_ID'
              value: fabricWorkspaceId
            }
            {
              name: 'FABRIC_LAKEHOUSE_ID'
              value: fabricLakehouseId
            }
            {
              name: 'FABRIC_SQL_SERVER'
              value: fabricSqlServer
            }
            {
              name: 'FABRIC_SQL_DATABASE'
              value: fabricSqlDatabase
            }
            {
              name: 'AZURE_SUBSCRIPTION_ID'
              value: azureSubscriptionId
            }
            {
              name: 'FABRIC_CAPACITY_RG'
              value: fabricCapacityResourceGroup
            }
            {
              name: 'FABRIC_CAPACITY_NAME'
              value: fabricCapacityName
            }
            {
              name: 'CORS_ORIGINS'
              value: 'http://localhost:5173,https://${web.properties.defaultHostname}'
            }
            {
              name: 'AZURE_TENANT_ID'
              value: tenantId
            }
            {
              name: 'API_AUDIENCE'
              value: apiAudience
            }
            {
              name: 'API_REQUIRED_SCOPE'
              value: apiRequiredScope
            }
            {
              name: 'WORK_IQ_CLIENT_ID'
              value: workIqClientId
            }
            {
              name: 'WORK_IQ_FUNDING_DOCUMENT_URLS'
              value: workIqFundingDocumentUrls
            }
            {
              name: 'WORK_IQ_FUNDING_DOCUMENT_IDENTITIES'
              value: workIqFundingDocumentIdentities
            }
            {
              name: 'APP_ENVIRONMENT'
              value: 'production'
            }
            {
              name: 'WORK_IQ_KEY_VAULT_URL'
              value: keyVaultUri
            }
            {
              name: 'WORK_IQ_CLIENT_CERTIFICATE_SECRET_NAME'
              value: workIqClientCertificateSecretName
            }
            {
              name: 'WORK_IQ_ENDPOINT'
              value: workIqEndpoint
            }
            {
              name: 'WORK_IQ_SCOPE'
              value: workIqScope
            }
            {
              name: 'USE_LIVE_FOUNDRY'
              value: useLiveFoundry ? 'true' : 'false'
            }
            {
              name: 'FOUNDRY_KS_NAME'
              value: foundryKsName
            }
            {
              name: 'SEARCH_API_VERSION'
              value: searchApiVersion
            }
            {
              name: 'USE_LIVE_FUNDING_LLM'
              value: useLiveFundingLlm ? 'true' : 'false'
            }
            {
              name: 'FOUNDRY_ENDPOINT'
              value: modelEndpoint
            }
            {
              name: 'MODEL_DEPLOYMENT'
              value: modelDeployment
            }
            {
              name: 'USE_LIVE_FABRIC'
              value: 'true'
            }
            {
              name: 'USE_LIVE_WORK'
              value: useLiveWork ? 'true' : 'false'
            }
          ]
        }
      ]
    }
  }
  dependsOn: [
    acrPullAssignment
  ]
}

output apiUrl string = 'https://${api.properties.configuration.ingress.fqdn}'
output staticWebAppUrl string = 'https://${web.properties.defaultHostname}'
output staticWebAppId string = web.id
output containerRegistryEndpoint string = containerRegistry.properties.loginServer

targetScope = 'resourceGroup'

param location string
param searchLocation string = location
param accountName string
param searchName string
param principalId string
param modelName string
param modelVersion string
param deploymentName string = 'award-iq-reasoning'
param modelCapacity int = 50
param tags object

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
  properties: {
    customSubDomainName: accountName
    allowProjectManagement: true
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: 'award-iq'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'Award IQ'
    description: 'Isolated synthetic funding-readiness knowledge and reasoning.'
  }
}

resource model 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: deploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
  dependsOn: [
    project
  ]
}

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: searchName
  location: searchLocation
  sku: {
    name: 'basic'
  }
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'Default'
    disableLocalAuth: true
    semanticSearch: 'free'
    publicNetworkAccess: 'enabled'
  }
}

module searchModelRole 'foundry-role.bicep' = {
  name: 'award-iq-search-model-role'
  params: {
    foundryAccountName: account.name
    principalId: search.identity.principalId
    roleAssignmentSeed: search.id
  }
}

module apiSearchRole 'search-role.bicep' = {
  name: 'award-iq-api-search-role'
  params: {
    searchServiceName: search.name
    principalId: principalId
    roleAssignmentSeed: principalId
  }
}

resource apiModelRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, principalId, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  scope: account
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  }
}

output searchEndpoint string = 'https://${search.name}.search.windows.net'
output modelEndpoint string = 'https://${account.name}.openai.azure.com'
output modelDeployment string = model.name
output projectResourceId string = project.id
output searchResourceId string = search.id
output modelResourceId string = account.id

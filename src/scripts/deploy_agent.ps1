# deploy_agent.ps1 - Deploy a hosted agent to Azure AI Foundry
#
# Usage:
#   .\scripts\deploy_agent.ps1 <agent_type> <model_id>
#
# Examples:
#   .\scripts\deploy_agent.ps1 retail o4-mini
#   .\scripts\deploy_agent.ps1 retail gpt-4.1
#   .\scripts\deploy_agent.ps1 retail gpt-4.1-mini
#   .\scripts\deploy_agent.ps1 retail o4-mini-finetuned
#
# Prerequisites:
#   - azd provisioned project (run from deploy/ the first time)
#   - Azure CLI logged in
#   - TOOL_URL env vars set (or defaults used)
#
# The script will:
#   1. Generate a concrete manifest from the template
#   2. Ensure the model deployment exists
#   3. Run azd deploy for the generated service
#   4. Grant the required role to the agent's instance identity

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$AgentType,

    [Parameter(Position = 1)]
    [string]$ModelId
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Show-Usage {
    Write-Host 'Usage: .\scripts\deploy_agent.ps1 <agent_type> <model_id>'
    Write-Host ''
    Write-Host 'Agent types: retail'
    Write-Host 'Model IDs:   o4-mini, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-5.4, gpt-5.4-mini'
    Write-Host ''
    Write-Host 'Examples:'
    Write-Host '  .\scripts\deploy_agent.ps1 retail o4-mini'
    Write-Host '  .\scripts\deploy_agent.ps1 retail gpt-4.1'
}

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw ('Command failed with exit code {0}. {1} {2}' -f $LASTEXITCODE, $FilePath, ($Arguments -join ' '))
    }
}

function Get-NativeCommandOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & $FilePath @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        $outputText = (($output | Out-String).Trim())
        if ($outputText) {
            throw ("Command failed with exit code {0}. {1} {2}`n{3}" -f $LASTEXITCODE, $FilePath, ($Arguments -join ' '), $outputText)
        }

        throw ('Command failed with exit code {0}. {1} {2}' -f $LASTEXITCODE, $FilePath, ($Arguments -join ' '))
    }

    return (($output | Out-String).Trim())
}

function Get-DotEnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    $line = Get-Content -LiteralPath $Path | Where-Object {
        $_ -match "^\s*$([regex]::Escape($Name))\s*="
    } | Select-Object -First 1

    if ([string]::IsNullOrWhiteSpace($line)) {
        return $null
    }

    $value = ($line -split '=', 2)[1].Trim()
    return $value.Trim('"').Trim("'")
}

function Get-ProjectEndpointParts {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Endpoint
    )

    $uri = [uri]$Endpoint.Trim().TrimEnd('/')
    $accountName = ($uri.Host -split '\.')[0]
    $pathParts = $uri.AbsolutePath.Trim('/') -split '/'
    $projectIndex = [array]::IndexOf($pathParts, 'projects')
    if ($projectIndex -lt 0 -or $projectIndex -ge ($pathParts.Length - 1)) {
        throw "PROJECT_ENDPOINT must be in the format https://{account}.services.ai.azure.com/api/projects/{project}."
    }

    return @{
        AccountName = $accountName
        ProjectName = $pathParts[$projectIndex + 1]
        Endpoint = $uri.ToString().TrimEnd('/')
    }
}

function Resolve-AzureAiAccount {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AccountName
    )

    $query = "resources | where name =~ '$AccountName' and type =~ 'microsoft.cognitiveservices/accounts' | project name, resourceGroup, subscriptionId, location, id | take 1"
    $json = Get-NativeCommandOutput -FilePath 'az' -Arguments @('graph', 'query', '-q', $query, '--first', '1', '-o', 'json')
    $result = $json | ConvertFrom-Json
    if (-not $result.data -or $result.data.Count -eq 0) {
        throw "Could not find Azure AI account '$AccountName' in accessible subscriptions. Run 'az login' or switch tenants, then retry."
    }

    return $result.data[0]
}

function Resolve-ContainerRegistry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SubscriptionId,

        [Parameter(Mandatory = $true)]
        [string]$ResourceGroup
    )

    $query = "resources | where subscriptionId == '$SubscriptionId' and resourceGroup =~ '$ResourceGroup' and type =~ 'microsoft.containerregistry/registries' | project name, id, loginServer=properties.loginServer | take 1"
    $json = Get-NativeCommandOutput -FilePath 'az' -Arguments @('graph', 'query', '-q', $query, '--first', '1', '-o', 'json')
    $result = $json | ConvertFrom-Json
    if (-not $result.data -or $result.data.Count -eq 0) {
        return $null
    }

    return $result.data[0]
}

function Initialize-AzdEnvironmentFromProjectEndpoint {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string]$DeployDir
    )

    $rootEnvPath = Join-Path $RepoRoot '.env'
    $projectEndpoint = Get-DotEnvValue -Path $rootEnvPath -Name 'PROJECT_ENDPOINT'
    if ([string]::IsNullOrWhiteSpace($projectEndpoint)) {
        throw "No azd environment found and PROJECT_ENDPOINT is not set in $rootEnvPath."
    }

    $endpointParts = Get-ProjectEndpointParts -Endpoint $projectEndpoint
    $account = Resolve-AzureAiAccount -AccountName $endpointParts.AccountName
    $tenantId = Get-NativeCommandOutput -FilePath 'az' -Arguments @('account', 'show', '--subscription', $account.subscriptionId, '--query', 'tenantId', '-o', 'tsv')
    $registry = Resolve-ContainerRegistry -SubscriptionId $account.subscriptionId -ResourceGroup $account.resourceGroup
    $projectId = "$($account.id)/projects/$($endpointParts.ProjectName)"
    $envName = $endpointParts.ProjectName -replace '^ai-project-', ''

    $deployAzdDir = Join-Path $DeployDir '.azure'
    $envDir = Join-Path $deployAzdDir $envName
    New-Item -ItemType Directory -Path $envDir -Force | Out-Null

    @{ version = 1; defaultEnvironment = $envName } |
        ConvertTo-Json -Compress |
        Set-Content -LiteralPath (Join-Path $deployAzdDir 'config.json') -NoNewline

    $envLines = @(
        "AZURE_ENV_NAME=`"$envName`"",
        "AZURE_SUBSCRIPTION_ID=`"$($account.subscriptionId)`"",
        "AZURE_TENANT_ID=`"$tenantId`"",
        "AZURE_RESOURCE_GROUP=`"$($account.resourceGroup)`"",
        "AZURE_LOCATION=`"$($account.location)`"",
        "AZURE_AI_DEPLOYMENTS_LOCATION=`"$($account.location)`"",
        "AZURE_AI_ACCOUNT_NAME=`"$($endpointParts.AccountName)`"",
        "AZURE_AI_PROJECT_NAME=`"$($endpointParts.ProjectName)`"",
        "AZURE_AI_PROJECT_ID=`"$projectId`"",
        "FOUNDRY_PROJECT_ENDPOINT=`"$($endpointParts.Endpoint)`"",
        "AZURE_OPENAI_ENDPOINT=`"https://$($endpointParts.AccountName).openai.azure.com/`"",
        'ENABLE_HOSTED_AGENTS="true"',
        'USE_EXISTING_AI_PROJECT="true"'
    )

    if ($registry) {
        $envLines += @(
            'AZD_AGENT_SKIP_ACR="false"',
            "AZURE_CONTAINER_REGISTRY_ENDPOINT=`"$($registry.loginServer)`"",
            "AZURE_CONTAINER_REGISTRY_RESOURCE_ID=`"$($registry.id)`""
        )
    }

    Set-Content -LiteralPath (Join-Path $envDir '.env') -Value $envLines

    Write-Host "Initialized azd environment '$envName' for $($endpointParts.AccountName) in $deployAzdDir"
}

function Get-ModelConfig {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Model
    )

    switch ($Model) {
        'o4-mini' {
            return @{ Sku = 'Standard'; Version = '2025-04-16'; Capacity = 50 }
        }
        'gpt-4.1' {
            return @{ Sku = 'DataZoneStandard'; Version = '2025-04-14'; Capacity = 50 }
        }
        'gpt-4.1-mini' {
            return @{ Sku = 'Standard'; Version = '2025-04-14'; Capacity = 50 }
        }
        'gpt-4.1-nano' {
            return @{ Sku = 'GlobalStandard'; Version = '2025-04-14'; Capacity = 50 }
        }
        'gpt-5.4' {
            return @{ Sku = 'GlobalStandard'; Version = '2026-03-05'; Capacity = 50 }
        }
        'gpt-5.4-mini' {
            return @{ Sku = 'GlobalStandard'; Version = '2026-03-17'; Capacity = 50 }
        }
        'retail-rft-v4' {
            return @{ Sku = 'GlobalStandard'; Version = '1'; Capacity = 100 }
        }
        default {
            throw "Unknown model '$Model'. Add it to Get-ModelConfig in this script."
        }
    }
}

if ([string]::IsNullOrWhiteSpace($AgentType) -or [string]::IsNullOrWhiteSpace($ModelId)) {
    Show-Usage
    exit 1
}

$ModelDeploymentName = $ModelId
$CreateModelIfMissing = $true

# Set tool URL
if ($env:TOOL_URL) {
    $ToolUrl = $env:TOOL_URL
}
else {
    $ToolUrl = 'https://retail-tools-omkarm.azurewebsites.net'
}

$modelConfig = Get-ModelConfig -Model $ModelDeploymentName

$ScriptDir = Split-Path -Parent $PSCommandPath
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir '..')).Path
$DeployDir = Join-Path $RepoRoot 'deploy'

$AgentDir = Join-Path $RepoRoot "agents\$AgentType"
$Template = Join-Path $AgentDir 'agent.manifest.yaml'

if (-not (Test-Path -LiteralPath $AgentDir -PathType Container)) {
    throw "Agent directory not found: $AgentDir"
}

if (-not (Test-Path -LiteralPath $Template -PathType Leaf)) {
    throw "Manifest template not found: $Template"
}

$DeployAzdDir = Join-Path $DeployDir '.azure'
Initialize-AzdEnvironmentFromProjectEndpoint -RepoRoot $RepoRoot -DeployDir $DeployDir

$SafeModelId = $ModelId -replace '\.', '-'
$ServiceName = "$AgentType-$SafeModelId"
$SrcDir = Join-Path $DeployDir "src\$ServiceName"

Write-Host '============================================'
Write-Host " Deploying: $ServiceName"
Write-Host " Model:     $ModelDeploymentName"
Write-Host " Tool URL:  $ToolUrl"
Write-Host " Source:    $SrcDir"
Write-Host '============================================'
Write-Host ''

Write-Host '[1/5] Updating source files...'
New-Item -ItemType Directory -Path $SrcDir -Force | Out-Null

$requiredSourceFiles = @('main.py', 'Dockerfile', 'requirements.txt')
foreach ($fileName in $requiredSourceFiles) {
    $sourcePath = Join-Path $AgentDir $fileName
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "Required source file not found: $sourcePath"
    }

    Copy-Item -LiteralPath $sourcePath -Destination $SrcDir -Force
}

$optionalSourceFiles = @('.agentignore', 'tracing.py')
foreach ($fileName in $optionalSourceFiles) {
    $sourcePath = Join-Path $AgentDir $fileName
    if (Test-Path -LiteralPath $sourcePath -PathType Leaf) {
        Copy-Item -LiteralPath $sourcePath -Destination $SrcDir -Force
    }
}

$manifest = Get-Content -LiteralPath $Template -Raw
$manifest = $manifest.Replace('{{MODEL_ID}}', $ModelDeploymentName).Replace('{{TOOL_URL}}', $ToolUrl)
$manifest = $manifest.Replace("name: $AgentType-$ModelDeploymentName", "name: $ServiceName")
Set-Content -LiteralPath (Join-Path $SrcDir 'agent.manifest.yaml') -Value $manifest -NoNewline

$agentYaml = @"
# yaml-language-server: `$schema=https://raw.githubusercontent.com/microsoft/AgentSchema/refs/heads/main/schemas/v1.0/ContainerAgent.yaml

kind: hosted
name: $ServiceName
description: |
    Retail agent ($ModelDeploymentName) with 6 tools for post-purchase resolution. Uses external tool server for policy lookup, inventory, and resolution processing.
metadata:
    tags:
    - AI Agent Hosting
    - Azure AI AgentServer
    - Multi-Tool
protocols:
    - protocol: responses
      version: 1.0.0
resources:
    cpu: "0.5"
    memory: 1Gi
environment_variables:
    - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
      value: $ModelDeploymentName
    - name: TOOL_URL
      value: $ToolUrl
"@
Set-Content -LiteralPath (Join-Path $SrcDir 'agent.yaml') -Value $agentYaml -NoNewline

Write-Host "  Updated: $SrcDir\main.py"
Write-Host "  Manifest: $SrcDir\agent.manifest.yaml"
Write-Host "  Agent: $SrcDir\agent.yaml"
Write-Host ''

Write-Host '[2/5] Ensuring model deployment exists...'
Push-Location $DeployDir
try {
    $SubscriptionId = Get-NativeCommandOutput -FilePath 'azd' -Arguments @('env', 'get-value', 'AZURE_SUBSCRIPTION_ID')
    $ResourceGroup = Get-NativeCommandOutput -FilePath 'azd' -Arguments @('env', 'get-value', 'AZURE_RESOURCE_GROUP')
    $AccountName = Get-NativeCommandOutput -FilePath 'azd' -Arguments @('env', 'get-value', 'AZURE_AI_ACCOUNT_NAME')

    Invoke-NativeCommand -FilePath 'az' -Arguments @('account', 'set', '--subscription', $SubscriptionId)

    & az cognitiveservices account deployment show --name $AccountName -g $ResourceGroup --deployment-name $ModelDeploymentName *> $null
    $modelExists = $LASTEXITCODE -eq 0

    if ($modelExists) {
        Write-Host "  Model deployment '$ModelDeploymentName' already exists [OK]"
    }
    else {
        if (-not $CreateModelIfMissing) {
            throw "Required model deployment '$ModelDeploymentName' was not found. Create it first, then retry."
        }

        Write-Host "  Deploying model '$ModelDeploymentName' (SKU: $($modelConfig.Sku), version: $($modelConfig.Version), capacity: $($modelConfig.Capacity))..."
        Invoke-NativeCommand -FilePath 'az' -Arguments @(
            'cognitiveservices', 'account', 'deployment', 'create',
            '--name', $AccountName,
            '--resource-group', $ResourceGroup,
            '--deployment-name', $ModelDeploymentName,
            '--model-name', $ModelDeploymentName,
            '--model-version', $modelConfig.Version,
            '--model-format', 'OpenAI',
            '--sku-capacity', [string]$modelConfig.Capacity,
            '--sku-name', $modelConfig.Sku,
            '--only-show-errors'
        )
        Write-Host "  Model '$ModelDeploymentName' deployed [OK]"
    }
    Write-Host ''

    Write-Host '[3/5] Deploying agent container...'
    Invoke-NativeCommand -FilePath 'azd' -Arguments @('deploy', $ServiceName, '--no-prompt')

    Write-Host ''
    Write-Host '[4/5] Granting role to agent instance identity...'
    Write-Host '  (Note: Role may already exist from a previous agent in the same project)'

    $agentShow = Get-NativeCommandOutput -FilePath 'azd' -Arguments @('ai', 'agent', 'show', $ServiceName)
    $instanceLine = $agentShow -split '\r?\n' | Where-Object { $_ -match 'Instance Identity Client ID' } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($instanceLine)) {
        throw "Could not get Instance Identity Client ID. Run 'azd ai agent show $ServiceName' manually to debug."
    }

    $InstanceId = (($instanceLine -split '\s+') | Select-Object -Last 1).Trim()
    if ([string]::IsNullOrWhiteSpace($InstanceId)) {
        throw "Could not parse Instance Identity Client ID. Run 'azd ai agent show $ServiceName' manually to debug."
    }

    $ProjectId = Get-NativeCommandOutput -FilePath 'azd' -Arguments @('env', 'get-value', 'AZURE_AI_PROJECT_ID')
    $AccountId = $ProjectId -replace '/projects/.*$', ''
    if ([string]::IsNullOrWhiteSpace($AccountId)) {
        throw 'Could not get account ID from AZURE_AI_PROJECT_ID'
    }

    Write-Host "  Instance ID: $InstanceId"
    Write-Host "  Account scope: $AccountId"

    & az role assignment create `
        --assignee-object-id $InstanceId `
        --assignee-principal-type ServicePrincipal `
        --role '53ca6127-db72-4b80-b1b0-d745d6d5456d' `
        --scope $AccountId `
        --only-show-errors 2>$null

    if ($LASTEXITCODE -ne 0) {
        Write-Host '  (Role already exists - OK)'
    }
}
finally {
    Pop-Location
}

Write-Host ''
Write-Host '[5/5] Deployment complete!'
Write-Host ''
Write-Host "  Agent name: $ServiceName"
Write-Host "  Model:      $ModelDeploymentName"
Write-Host ''
Write-Host '  [WARN] Role propagation takes 3-5 minutes.'
Write-Host '  Test with:'
Write-Host ('    cd {0}; azd ai agent invoke --message "Hello, what can you help me with?"' -f $DeployDir)
Write-Host ''
Write-Host '============================================'

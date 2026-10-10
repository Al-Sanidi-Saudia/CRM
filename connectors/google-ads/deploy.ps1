<#
.SYNOPSIS
  Creates (or updates) the Google Ads custom connector inside the
  "AlSanidi | Marketing" solution using the Power Platform CLI (pac).

.EXAMPLE
  .\deploy.ps1 -EnvironmentUrl https://operations-alsenidiuat.crm4.dynamics.com -GoogleClientId 123.apps.googleusercontent.com -DeveloperToken abc

.EXAMPLE
  # Update an existing connector (ID from: pac connector list)
  .\deploy.ps1 -EnvironmentUrl https://operations-alsenidiuat.crm4.dynamics.com -GoogleClientId 123.apps.googleusercontent.com -DeveloperToken abc -ConnectorId 00000000-0000-0000-0000-000000000000
#>
param(
    [Parameter(Mandatory = $true)] [string] $EnvironmentUrl,
    [Parameter(Mandatory = $true)] [string] $GoogleClientId,
    # Google Ads developer token (Google Ads > Tools > API Center). Never commit it.
    [Parameter(Mandatory = $true)] [string] $DeveloperToken,
    # Unique (not display) name of "AlSanidi | Marketing"; find it with: pac solution list
    [string] $SolutionUniqueName = "AlSanidiMarketing",
    [string] $ConnectorId
)
$ErrorActionPreference = "Stop"

if (-not (Get-Command pac -ErrorAction SilentlyContinue)) {
    throw "pac CLI not found. Install it: https://aka.ms/PowerPlatformCLI"
}

$dir = $PSScriptRoot
$tmp = [IO.Path]::GetTempPath()
$props = Join-Path $tmp "googleads-apiProperties.json"
$script = Join-Path $tmp "googleads-script.csx"
(Get-Content (Join-Path $dir "apiProperties.json") -Raw).Replace("REPLACE_WITH_GOOGLE_CLIENT_ID", $GoogleClientId) |
    Set-Content -Path $props -Encoding utf8
(Get-Content (Join-Path $dir "script.csx") -Raw).Replace("REPLACE_WITH_DEVELOPER_TOKEN", $DeveloperToken) |
    Set-Content -Path $script -Encoding utf8

# Sign in only if there is no auth profile yet (opens a browser).
pac org who *> $null
if ($LASTEXITCODE -ne 0) {
    pac auth create --environment $EnvironmentUrl
    if ($LASTEXITCODE -ne 0) { throw "pac auth create failed" }
}

# Read the publisher prefix of the target solution. Creating the connector inside this
# solution gives its internal name that prefix (e.g. <prefix>_googleads).
$fetch = "<fetch top='1'><entity name='solution'><attribute name='uniquename'/>" +
         "<filter><condition attribute='uniquename' operator='eq' value='$SolutionUniqueName'/></filter>" +
         "<link-entity name='publisher' from='publisherid' to='publisherid' alias='pub'>" +
         "<attribute name='customizationprefix'/></link-entity></entity></fetch>"
$fetchOut = pac env fetch --environment $EnvironmentUrl --xml $fetch 2>&1 | Out-String
$row = ($fetchOut -split "`r?`n") | Where-Object { $_ -match "^\s*$([regex]::Escape($SolutionUniqueName))\s+" } | Select-Object -First 1
if (-not $row) {
    Write-Host $fetchOut
    throw "Solution '$SolutionUniqueName' not found. Run 'pac solution list' and pass its Unique Name with -SolutionUniqueName."
}
$prefix = (($row.Trim() -split "\s+") | Select-Object -Last 1).ToLower()
Write-Host "Solution '$SolutionUniqueName' uses publisher prefix '$prefix'."

$common = @(
    "--api-definition-file", (Join-Path $dir "apiDefinition.swagger.json"),
    "--api-properties-file", $props,
    "--script-file", $script,
    "--solution-unique-name", $SolutionUniqueName,
    "--environment", $EnvironmentUrl
)
try {
    if ($ConnectorId) {
        pac connector update --connector-id $ConnectorId @common
    } else {
        pac connector create @common
    }
    if ($LASTEXITCODE -ne 0) { throw "pac connector command failed (see output above)" }
} finally {
    # The script copy holds the developer token.
    Remove-Item $props, $script -ErrorAction SilentlyContinue
}

# Confirm the internal name carries the publisher prefix.
$connectors = pac connector list --environment $EnvironmentUrl --json 2>$null | Out-String | ConvertFrom-Json -ErrorAction SilentlyContinue
$gads = @($connectors) | Where-Object { $_.PSObject.Properties.Value -contains "Google Ads" } | Select-Object -First 1
if ($gads) {
    $gads | Format-List | Out-String | Write-Host
    $internal = @($gads.PSObject.Properties.Value) | Where-Object { $_ -is [string] -and $_ -match "^${prefix}_" }
    if ($internal) {
        Write-Host "Internal name '$($internal[0])' uses prefix '$prefix'."
    } else {
        Write-Warning "The connector's internal name does not start with '${prefix}_'. Check the solution's publisher."
    }
} else {
    Write-Warning "Could not find the 'Google Ads' connector in 'pac connector list' to verify its internal name."
}

Write-Host "Done. Next: open the connector in make.powerapps.com, enter the Google client secret on the"
Write-Host "Security tab, Update connector, then add the shown Redirect URL to the Google OAuth client."

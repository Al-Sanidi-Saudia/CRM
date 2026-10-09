<#
.SYNOPSIS
  Creates (or updates) the Snapchat Ads custom connector inside the
  "AlSanidi | Marketing" solution using the Power Platform CLI (pac).

.EXAMPLE
  .\deploy.ps1 -EnvironmentUrl https://alsanidi.crm4.dynamics.com -SnapClientId abc123

.EXAMPLE
  # Update an existing connector (ID from: pac connector list)
  .\deploy.ps1 -EnvironmentUrl https://alsanidi.crm4.dynamics.com -SnapClientId abc123 -ConnectorId 00000000-0000-0000-0000-000000000000
#>
param(
    [Parameter(Mandatory = $true)] [string] $EnvironmentUrl,
    [Parameter(Mandatory = $true)] [string] $SnapClientId,
    # Unique (not display) name of "AlSanidi | Marketing"; find it with: pac solution list
    [string] $SolutionUniqueName = "AlSanidiMarketing",
    [string] $ConnectorId
)
$ErrorActionPreference = "Stop"

if (-not (Get-Command pac -ErrorAction SilentlyContinue)) {
    throw "pac CLI not found. Install it: https://aka.ms/PowerPlatformCLI"
}

$dir = $PSScriptRoot
$props = Join-Path ([IO.Path]::GetTempPath()) "snapchat-apiProperties.json"
(Get-Content (Join-Path $dir "apiProperties.json") -Raw).Replace("REPLACE_WITH_SNAP_CLIENT_ID", $SnapClientId) |
    Set-Content -Path $props -Encoding utf8

# Sign in only if there is no auth profile yet (opens a browser).
pac org who *> $null
if ($LASTEXITCODE -ne 0) {
    pac auth create --environment $EnvironmentUrl
    if ($LASTEXITCODE -ne 0) { throw "pac auth create failed" }
}

$common = @(
    "--api-definition-file", (Join-Path $dir "apiDefinition.swagger.json"),
    "--api-properties-file", $props,
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
    Remove-Item $props -ErrorAction SilentlyContinue
}

Write-Host "Done. Next: open the connector in make.powerapps.com, enter the Snap client secret on the"
Write-Host "Security tab, Update connector, then register the shown Redirect URL in the Snap OAuth app."

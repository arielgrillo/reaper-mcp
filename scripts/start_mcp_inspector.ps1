$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ErrorActionPreference = "Stop"

Set-Location $repositoryRoot

Write-Host "Starting MCP Inspector from $repositoryRoot..."

try {
    & npx "@modelcontextprotocol/inspector"
    $inspectorExitCode = $LASTEXITCODE
}
catch {
    Write-Error "Failed to start MCP Inspector: $_"
    exit 1
}

exit $inspectorExitCode

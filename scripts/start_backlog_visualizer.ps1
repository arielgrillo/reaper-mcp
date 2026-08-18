$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ErrorActionPreference = "Stop"

Set-Location $repositoryRoot

Write-Host "Starting backlog visualizer from $repositoryRoot..."

try {
    & uv run python -m http.server 8000 --directory tasks
    $visualizerExitCode = $LASTEXITCODE
}
catch {
    Write-Error "Failed to start backlog visualizer: $_"
    exit 1
}

exit $visualizerExitCode

# One-command demo prep: build stack, wait for health, seed 12/12 scenarios.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> Starting Docker Compose stack …"
docker compose up --build -d

Write-Host "==> Waiting for API health …"
$healthy = $false
for ($i = 1; $i -le 30; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5
        if ($resp.StatusCode -eq 200) {
            Write-Host "    API healthy after $i attempt(s)."
            $healthy = $true
            break
        }
    } catch {
        # retry
    }
    Start-Sleep -Seconds 2
}
if (-not $healthy) {
    Write-Error "API did not become healthy within 30 attempts."
}

Write-Host "==> Seeding 12 mandatory + 2 supplementary scenarios …"
docker exec gnani-emi-api python scripts/seed_scenarios.py --base-url http://localhost:8000

Write-Host ""
Write-Host "Demo ready."
Write-Host "  Dashboard : http://localhost:8000/"
Write-Host "  Swagger   : http://localhost:8000/docs"
Write-Host "  Health    : http://localhost:8000/health"
Write-Host "  Demo guide: docs/DEMO.md"
Write-Host ""
try {
    (Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing).Content
} catch {
    Write-Host "(Could not fetch /health JSON — open the URL in a browser.)"
}

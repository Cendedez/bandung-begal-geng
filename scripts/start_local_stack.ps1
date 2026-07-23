[CmdletBinding()]
param(
    [int]$ApiPort = 8000,
    [string]$ApiHost = "127.0.0.1",
    [switch]$SkipDatabase,
    [switch]$SkipTunnel,
    [switch]$DeployVercel
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WebDir = Join-Path $ProjectRoot "web"
$RuntimeDir = Join-Path $ProjectRoot "tmp\runtime"
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$NgrokPath = Join-Path $ProjectRoot "ngrok.exe"
$ApiBaseUrl = "http://${ApiHost}:${ApiPort}"
$ApiHealthUrl = "$ApiBaseUrl/health"
$NgrokApiUrl = "http://127.0.0.1:4040/api/tunnels"

New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-HttpOk([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return [int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 300
    } catch {
        return $false
    }
}

function Wait-HttpOk([string]$Url, [int]$Seconds, [string]$Name) {
    for ($i = 0; $i -lt $Seconds; $i++) {
        if (Test-HttpOk $Url) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    throw "$Name did not become ready at $Url"
}

function Get-NgrokHttpsUrl {
    try {
        $tunnels = Invoke-RestMethod -Uri $NgrokApiUrl -TimeoutSec 3
        $httpsTunnel = $tunnels.tunnels |
            Where-Object { $_.proto -eq "https" -and $_.public_url } |
            Select-Object -First 1
        if ($httpsTunnel) {
            return $httpsTunnel.public_url
        }
    } catch {
        return $null
    }
    return $null
}

Set-Location $ProjectRoot

if (-not $SkipDatabase) {
    Write-Step "Starting PostGIS database"
    docker compose up -d database
}

Write-Step "Starting FastAPI backend"
if (Test-HttpOk $ApiHealthUrl) {
    Write-Host "FastAPI is already running at $ApiBaseUrl"
} else {
    if (-not (Test-Path $PythonPath)) {
        throw "Python virtualenv was not found at $PythonPath. Create it first, then install requirements-api.txt."
    }

    $apiOut = Join-Path $RuntimeDir "fastapi.out.log"
    $apiErr = Join-Path $RuntimeDir "fastapi.err.log"
    $apiProcess = Start-Process `
        -FilePath $PythonPath `
        -ArgumentList @("-m", "uvicorn", "api.main:app", "--host", $ApiHost, "--port", "$ApiPort") `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $apiOut `
        -RedirectStandardError $apiErr `
        -PassThru
    $apiProcess.Id | Set-Content -Path (Join-Path $RuntimeDir "fastapi.pid")
    Wait-HttpOk $ApiHealthUrl 30 "FastAPI"
    Write-Host "FastAPI started at $ApiBaseUrl"
    Write-Host "Logs: $apiOut"
}

$publicApiUrl = $null
if (-not $SkipTunnel) {
    Write-Step "Starting Ngrok tunnel"
    $publicApiUrl = Get-NgrokHttpsUrl
    if ($publicApiUrl) {
        Write-Host "Ngrok is already running: $publicApiUrl"
    } else {
        if (-not (Test-Path $NgrokPath)) {
            throw "ngrok.exe was not found at $NgrokPath"
        }

        $ngrokOut = Join-Path $RuntimeDir "ngrok.out.log"
        $ngrokErr = Join-Path $RuntimeDir "ngrok.err.log"
        $ngrokProcess = Start-Process `
            -FilePath $NgrokPath `
            -ArgumentList @("http", $ApiBaseUrl, "--log=stdout") `
            -WorkingDirectory $ProjectRoot `
            -WindowStyle Hidden `
            -RedirectStandardOutput $ngrokOut `
            -RedirectStandardError $ngrokErr `
            -PassThru
        $ngrokProcess.Id | Set-Content -Path (Join-Path $RuntimeDir "ngrok.pid")

        for ($i = 0; $i -lt 30; $i++) {
            $publicApiUrl = Get-NgrokHttpsUrl
            if ($publicApiUrl) {
                break
            }
            Start-Sleep -Seconds 1
        }

        if (-not $publicApiUrl) {
            throw "Ngrok did not expose a public HTTPS URL. Check $ngrokErr"
        }
        Write-Host "Ngrok started: $publicApiUrl"
        Write-Host "Logs: $ngrokOut"
    }
}

if ($DeployVercel) {
    if (-not $publicApiUrl) {
        throw "-DeployVercel requires a tunnel URL. Run without -SkipTunnel."
    }

    Write-Step "Deploying Vercel frontend with INTERNAL_API_URL=$publicApiUrl"
    Set-Location $WebDir
    npx vercel@latest deploy --prod --yes --build-env "INTERNAL_API_URL=$publicApiUrl" --env "INTERNAL_API_URL=$publicApiUrl"
    Set-Location $ProjectRoot
}

Write-Step "Ready"
Write-Host "Backend local : $ApiBaseUrl"
if ($publicApiUrl) {
    Write-Host "Backend public: $publicApiUrl"
}
Write-Host "Frontend     : https://web-theta-pink-72.vercel.app"
Write-Host ""
Write-Host "Quick checks:"
Write-Host "  Invoke-RestMethod $ApiHealthUrl"
if ($publicApiUrl) {
    Write-Host "  Invoke-RestMethod https://web-theta-pink-72.vercel.app/api/v1/incidents"
}

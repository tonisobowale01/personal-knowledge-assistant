param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$pythonExecutable = Join-Path $projectDirectory '.venv\Scripts\python.exe'
$logDirectory = Join-Path $projectDirectory '.run'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Python environment missing. Follow the one-time setup in README.md.'
}
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null

try { $models = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5 }
catch { throw 'Open Ollama first, then run Start-Ash.ps1 again. See README.md for setup.' }
foreach ($modelName in @('llama3.2:3b', 'nomic-embed-text')) {
    if (-not ($models.models | Where-Object { $_.name -eq $modelName -or $_.name -eq "${modelName}:latest" })) {
        throw "Missing Ollama model: $modelName. Run: ollama pull $modelName"
    }
}

function Start-LocalService($serviceName, $healthUrl, $portNumber, $argumentList) {
    try {
        $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 3
        $healthy = if ($serviceName -eq 'backend') {
            ($response.Content | ConvertFrom-Json).PSObject.Properties.Name -contains 'courses'
        } else { $response.Content -match '<title>Personal Knowledge Assistant</title>' }
        if (-not $healthy) { throw "Another application appears to be using port $portNumber." }
        Write-Host "$serviceName is already running."
        return
    } catch {
        if (Get-NetTCPConnection -LocalPort $portNumber -State Listen -ErrorAction SilentlyContinue) {
            throw "Port $portNumber is busy but Ash did not respond correctly. Check the existing process before retrying."
        }
    }
    $process = Start-Process -FilePath $pythonExecutable -ArgumentList $argumentList `
        -WorkingDirectory $projectDirectory -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logDirectory "$serviceName.stdout.log") `
        -RedirectStandardError (Join-Path $logDirectory "$serviceName.stderr.log")
    $process.Id | Set-Content (Join-Path $logDirectory "$serviceName.pid")
    $deadline = (Get-Date).AddSeconds(45)
    do {
        Start-Sleep -Milliseconds 500
        try {
            $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { Write-Host "$serviceName started."; return }
        } catch { }
        $process.Refresh()
        if ($process.HasExited) { break }
    } while ((Get-Date) -lt $deadline)
    throw "$serviceName did not start. Check .run/$serviceName.stderr.log."
}

Start-LocalService 'backend' 'http://127.0.0.1:8000/courses' 8000 @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000')
Start-LocalService 'frontend' 'http://127.0.0.1:3000/' 3000 @('-m','http.server','3000','--bind','127.0.0.1','--directory','frontend')
Write-Host 'Ash is ready at http://127.0.0.1:3000'
Write-Host 'Logs are in .run/. Closing this console leaves Ash running.'
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:3000' }

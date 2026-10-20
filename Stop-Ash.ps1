$ErrorActionPreference = 'Stop'
$pythonExecutable = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
foreach ($service in @(@{Port=8000; Module='-m uvicorn app.main:app'}, @{Port=3000; Module='-m http.server 3000'})) {
    $listeners = Get-NetTCPConnection -LocalPort $service.Port -State Listen -ErrorAction SilentlyContinue
    foreach ($processId in @($listeners.OwningProcess | Select-Object -Unique)) {
        if (-not $processId) { continue }
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId"
        if ($process.CommandLine -match [regex]::Escape($pythonExecutable) -and
            $process.CommandLine -match [regex]::Escape($service.Module)) {
            Stop-Process -Id $processId -ErrorAction Stop
            Write-Host "Stopped Ash on port $($service.Port)."
        } else {
            Write-Warning "Port $($service.Port) belongs to another process; left it running."
        }
    }
}
Write-Host 'Ollama and your saved data were left in place.'

$root = $PSScriptRoot

# Shared storage directory - the .NET API writes uploads, the worker reads them. MUST be the same.
$storage = "$root\storage"

# Infrastructure: Postgres (shared database) + Redis (job queue).
Write-Host "Starting infrastructure (Postgres + Redis)..."
docker compose -f "$root\docker-compose.infra.yml" up -d | Out-Null

# .NET API (:8000) - creates the DB schema, listens on port 8000.
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$root\api-dotnet';
    `$env:STORAGE_DIR='$storage';
    dotnet run
" -WindowStyle Normal

# Python worker (vision) - pops jobs from Redis (BRPOP), writes to the shared Postgres.
# Creates .venv and installs dependencies on first run. Calls the venv's python.exe
# directly (more reliable than activate).
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$root\worker';
    if (-not (Test-Path .venv)) {
        Write-Host 'Creating .venv and installing dependencies (ultralytics/torch - this takes a while)...';
        python -m venv .venv;
        .\.venv\Scripts\python.exe -m pip install --upgrade pip;
        .\.venv\Scripts\python.exe -m pip install -r requirements.txt;
    }
    `$env:DATABASE_URL='postgresql+asyncpg://pitchwise:pitchwise@localhost:5432/pitchwise';
    `$env:REDIS_URL='redis://localhost:6379';
    `$env:STORAGE_DIR='$storage';
    `$env:WEB_ORIGIN='http://localhost:3000';
    # Use the winget-installed ffmpeg 8.x (has -hls_flags). Without this, an old
    # ffmpeg earlier on PATH (e.g. Panda3D's 2013 build) breaks live HLS encoding.
    `$ff = Get-ChildItem `"`$env:LOCALAPPDATA\Microsoft\WinGet\Packages`" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1;
    if (`$ff) { `$env:FFMPEG_PATH = `$ff.FullName };
    `$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path;
    Start-Job -ScriptBlock { param(`$p) & `$p -m app.worker } -ArgumentList `$python | Out-Null;
    & `$python -m uvicorn live.server:app --host 127.0.0.1 --port 8001
" -WindowStyle Normal

# Frontend (:3000) - NEXT_PUBLIC_API_URL points to http://localhost:8000.
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$root\web';
    npm run dev
" -WindowStyle Normal

Write-Host "Started:"
Write-Host "  API (.NET)      -> http://localhost:8000"
Write-Host "  Worker (Python) -> Redis 'vision_jobs' queue + live WebSocket :8001"
Write-Host "  Web             -> http://localhost:3000"
Write-Host "  Postgres        -> localhost:5432   Redis -> localhost:6379"

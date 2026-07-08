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

# .NET worker (vision) - pops jobs from Redis (BRPOP), writes to the shared Postgres,
# and serves the live WS/HLS server on :8001. Two processes (PitchWise.Worker batch +
# PitchWise.Live), no Python. YOLO11 runs via ONNX Runtime; ffmpeg does HLS.
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$root\worker-dotnet';
    # Shared with the .NET API (owns the schema): Npgsql connection string, NOT asyncpg.
    `$env:DATABASE_CONNECTION='Host=localhost;Port=5432;Database=pitchwise;Username=pitchwise;Password=pitchwise';
    `$env:REDIS_URL='redis://localhost:6379';
    `$env:STORAGE_DIR='$storage';
    `$env:WEB_ORIGIN='http://localhost:3000';
    # Exported YOLO11 ONNX + its .names.json sidecar. Swap to football.onnx for
    # production ball detection (see worker-dotnet/README.md).
    `$env:YOLO_MODEL_PATH='$root\worker-dotnet\vision-onnx\yolo11n.onnx';
    # Live pipeline: 'passthrough' (raw frames) or 'detect' (YOLO overlay). Default safe.
    `$env:LIVE_PIPELINE_MODE='detect';
    # Use the winget-installed ffmpeg 8.x (has -hls_flags). Without this, an old
    # ffmpeg earlier on PATH (e.g. Panda3D's 2013 build) breaks live HLS encoding.
    `$ff = Get-ChildItem `"`$env:LOCALAPPDATA\Microsoft\WinGet\Packages`" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1;
    if (`$ff) { `$env:FFMPEG_PATH = `$ff.FullName };
    # Batch worker in the background; live server in the foreground (keeps window alive).
    Start-Job -ScriptBlock {
        param(`$dir, `$db, `$redis, `$storage, `$model, `$ffmpeg)
        Set-Location `$dir;
        `$env:DATABASE_CONNECTION=`$db; `$env:REDIS_URL=`$redis; `$env:STORAGE_DIR=`$storage;
        `$env:YOLO_MODEL_PATH=`$model; if (`$ffmpeg) { `$env:FFMPEG_PATH=`$ffmpeg };
        dotnet run --project PitchWise.Worker -c Release
    } -ArgumentList (Get-Location).Path, `$env:DATABASE_CONNECTION, `$env:REDIS_URL, `$env:STORAGE_DIR, `$env:YOLO_MODEL_PATH, `$env:FFMPEG_PATH | Out-Null;
    dotnet run --project PitchWise.Live -c Release
" -WindowStyle Normal

# Frontend (:3000) - NEXT_PUBLIC_API_URL points to http://localhost:8000.
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$root\web';
    npm run dev
" -WindowStyle Normal

Write-Host "Started:"
Write-Host "  API (.NET)      -> http://localhost:8000"
Write-Host "  Worker (.NET)   -> Redis 'vision_jobs' queue + live WebSocket :8001"
Write-Host "  Web             -> http://localhost:3000"
Write-Host "  Postgres        -> localhost:5432   Redis -> localhost:6379"

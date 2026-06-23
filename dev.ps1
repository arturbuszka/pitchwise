$root = $PSScriptRoot

# Wspolny katalog storage - .NET API zapisuje uploady, worker je czyta. MUSI byc ten sam.
$storage = "$root\storage"

# Infrastruktura: Postgres (wspolna baza) + Redis (kolejka jobow).
Write-Host "Startuje infrastrukture (Postgres + Redis)..."
docker compose -f "$root\docker-compose.infra.yml" up -d | Out-Null

# .NET API (:8000) - tworzy schemat DB, ten sam port co dawniej (front bez zmian).
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$root\api-dotnet';
    `$env:STORAGE_DIR='$storage';
    dotnet run
" -WindowStyle Normal

# Worker Python (vision) - zdejmuje joby z Redis (BRPOP), pisze do wspolnego Postgresa.
# Tworzy .venv i instaluje zaleznosci przy pierwszym uruchomieniu. Wola python.exe z
# venv bezposrednio (pewniejsze niz activate).
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$root\worker';
    if (-not (Test-Path .venv)) {
        Write-Host 'Tworze .venv i instaluje zaleznosci (ultralytics/torch - chwile potrwa)...';
        python -m venv .venv;
        .\.venv\Scripts\python.exe -m pip install --upgrade pip;
        .\.venv\Scripts\python.exe -m pip install -r requirements.txt;
    }
    `$env:DATABASE_URL='postgresql+asyncpg://pitchwise:pitchwise@localhost:5432/pitchwise';
    `$env:REDIS_URL='redis://localhost:6379';
    `$env:STORAGE_DIR='$storage';
    .\.venv\Scripts\python.exe -m app.worker
" -WindowStyle Normal

# Frontend (:3000) - NEXT_PUBLIC_API_URL nadal wskazuje http://localhost:8000.
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$root\web';
    npm run dev
" -WindowStyle Normal

Write-Host "Uruchomiono:"
Write-Host "  API (.NET)      -> http://localhost:8000"
Write-Host "  Worker (Python) -> nasluch kolejki Redis 'vision_jobs'"
Write-Host "  Web             -> http://localhost:3000"
Write-Host "  Postgres        -> localhost:5432   Redis -> localhost:6379"

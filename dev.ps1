$root = $PSScriptRoot

Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$root\api';
    .\.venv\Scripts\activate;
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
" -WindowStyle Normal

Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$root\web';
    npm run dev
" -WindowStyle Normal

Write-Host "Uruchomiono:"
Write-Host "  API  -> http://localhost:8000"
Write-Host "  Web  -> http://localhost:3000"

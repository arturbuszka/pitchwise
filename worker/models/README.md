# Vision models

This directory holds the YOLO weights the worker loads for detection. It is intentionally
kept out of normal git tracking (`*.pt` is ignored) — fetch the model locally instead.

The default config (`YOLO_MODEL_PATH=models/football.pt`) expects a **football-specific**
model with the classes `ball`, `goalkeeper`, `player`, `referee` (the Roboflow
`football-players-detection` dataset). This fixes the main weakness of the COCO `yolo11n.pt`:
COCO loses the small, fast ball, which produces false "goal" events (see `vision/events.py`).

If `models/football.pt` is missing the worker **falls back to `yolo11n.pt`** automatically
(downloaded by ultralytics on first use), so dev still runs — just with worse ball detection.

## Fetch the model

You need a free Roboflow account + API key (https://app.roboflow.com → Settings → API key).

```powershell
# from the worker/ directory, inside the .venv
$env:ROBOFLOW_API_KEY = "<your-key>"
python -m models.fetch_model
```

This downloads the trained weights to `models/football.pt`. Re-run only when you want to
refresh the model. After fetching, restart the worker (`.\dev.ps1` worker window) — no rebuild.

## Class names

After downloading, confirm the model's class names match what the detector maps
(`vision/detector.py` → `_CLASS_ALIASES`). The fetch script prints them. Expected:
`ball`, `goalkeeper`, `player`, `referee` (order/indices may vary — only the names matter).

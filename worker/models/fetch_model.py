"""Fetch the football-specific YOLO weights into worker/models/football.pt.

Pulls the trained model from the Roboflow `football-players-detection` project (the same
weights used by the popular football_analysis tutorials) and copies them to the path the
worker loads by default (config: YOLO_MODEL_PATH=models/football.pt).

Usage (from worker/, inside .venv):
    $env:ROBOFLOW_API_KEY = "<key>"
    python -m models.fetch_model

Re-run to refresh. The worker falls back to COCO yolo11n.pt when this file is absent, so
this step is optional for getting the app running — but required for good ball detection.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# Roboflow Universe project that hosts the trained football model. Override via env if you
# point at a different workspace/project/version.
WORKSPACE = os.environ.get("ROBOFLOW_WORKSPACE", "roboflow-jvuqo")
PROJECT = os.environ.get("ROBOFLOW_PROJECT", "football-players-detection-3zvbc")
VERSION = int(os.environ.get("ROBOFLOW_VERSION", "12"))

DEST = Path(__file__).resolve().parent / "football.pt"


def main() -> int:
    api_key = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    if not api_key:
        print(
            "ROBOFLOW_API_KEY is not set. Get a free key at "
            "https://app.roboflow.com (Settings -> API key), then:\n"
            '    $env:ROBOFLOW_API_KEY = "<key>"',
            file=sys.stderr,
        )
        return 2

    try:
        from roboflow import Roboflow  # optional dep, imported lazily
    except ModuleNotFoundError:
        print(
            "The `roboflow` package is required to fetch the model:\n"
            "    pip install roboflow",
            file=sys.stderr,
        )
        return 2

    print(f"Fetching {WORKSPACE}/{PROJECT} v{VERSION} from Roboflow ...")
    rf = Roboflow(api_key=api_key)
    version = rf.workspace(WORKSPACE).project(PROJECT).version(VERSION)

    # download("yolov8") returns a dataset dir; the trained weights live in the deployed
    # model. Roboflow exposes them via model.weights_path after a deploy/download. We use
    # the dataset download to also surface the class names for verification.
    model = version.model
    weights_path = getattr(model, "weights_path", None)
    if not weights_path or not Path(weights_path).is_file():
        print(
            "Could not resolve a local weights file from the Roboflow model. "
            "Download the YOLO weights manually from the project's Deploy tab and place "
            f"them at {DEST}.",
            file=sys.stderr,
        )
        return 1

    DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(weights_path, DEST)
    print(f"Saved model to {DEST}")

    # Print class names so the operator can confirm they match _CLASS_ALIASES.
    try:
        from ultralytics import YOLO

        names = YOLO(str(DEST)).names
        print(f"Model classes: {names}")
    except Exception as exc:  # noqa: BLE001
        print(f"(Could not read class names: {exc})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Object detection + tracking on video frames.

Stack: ultralytics (YOLO11) for detection + supervision (ByteTrack) for tracking.
Roboflow `sports` / Roboflow Universe `football-players-detection` provide a trained
model (players/ball/referee). Without a model path we use the default `yolo11n.pt` —
it detects the COCO "sports ball" and "person" classes, which is enough for an
initial pipeline, but production needs a football-specific model.

Heavy imports (torch/ultralytics) are lazy so the rest of the API can start without them.
"""
from collections.abc import Iterator

from vision.types import (
    CLASS_BALL,
    CLASS_GOAL,
    CLASS_PLAYER,
    CLASS_REFEREE,
    Detection,
    FrameResult,
)

# Maps model class names onto our categories. Covers both football-specific models
# (player/ball/referee/goalkeeper) and the default COCO (person/sports ball).
_CLASS_ALIASES = {
    "ball": CLASS_BALL,
    "sports ball": CLASS_BALL,
    "player": CLASS_PLAYER,
    "person": CLASS_PLAYER,
    "referee": CLASS_REFEREE,
    "goalkeeper": "goalkeeper",
    # Stage 2 hook: active only when a football-specific model returns a goal class.
    "goal": CLASS_GOAL,
    "goalpost": CLASS_GOAL,
}


class Detector:
    def __init__(self, model_path: str | None, frame_stride: int = 5):
        self.model_path = model_path or "yolo11n.pt"
        self.frame_stride = max(1, frame_stride)
        self._model = None
        self._tracker = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        from ultralytics import YOLO  # lazy import (heavy)
        import supervision as sv

        self._model = YOLO(self.model_path)
        self._tracker = sv.ByteTrack()
        self._sv = sv

    def _map_class(self, raw_name: str) -> str | None:
        return _CLASS_ALIASES.get(raw_name.lower())

    def run(self, video_path: str) -> Iterator[FrameResult]:
        """Iterates over frames (every `frame_stride`) and yields detections with track_id."""
        self._ensure_loaded()
        sv = self._sv

        frames = sv.get_video_frames_generator(video_path, stride=self.frame_stride)
        info = sv.VideoInfo.from_video_path(video_path)
        fps = info.fps or 25.0

        for i, frame in enumerate(frames):
            frame_index = i * self.frame_stride
            timestamp = frame_index / fps

            result = self._model(frame, verbose=False)[0]
            sv_det = sv.Detections.from_ultralytics(result)
            sv_det = self._tracker.update_with_detections(sv_det)

            detections: list[Detection] = []
            names = result.names  # {class_id: name}
            for j in range(len(sv_det)):
                raw_name = names.get(int(sv_det.class_id[j]), "")
                cls = self._map_class(raw_name)
                if cls is None:
                    continue
                x1, y1, x2, y2 = (float(v) for v in sv_det.xyxy[j])
                track_id = (
                    int(sv_det.tracker_id[j])
                    if sv_det.tracker_id is not None
                    else None
                )
                detections.append(
                    Detection(
                        cls=cls,
                        xyxy=(x1, y1, x2, y2),
                        confidence=float(sv_det.confidence[j]),
                        track_id=track_id,
                    )
                )

            yield FrameResult(
                frame_index=frame_index,
                timestamp_seconds=timestamp,
                detections=detections,
            )

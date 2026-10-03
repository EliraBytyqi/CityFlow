"""Background YOLO workers for configured live camera streams."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app.database import SessionLocal
from app.models import Camera
from app.schemas import DetectionIngestion
from app.services.traffic_ingestion import TrafficModelAdapter


class CameraInference:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.camera_id: str | None = None
        self.status = "stopped"
        self.error: str | None = None
        self.counts = {"cars": 0, "trucks": 0, "buses": 0, "motorcycles": 0}
        self.updated_at: str | None = None
        self.annotated_frame: bytes | None = None

    def snapshot(self):
        return {"camera_id": self.camera_id, "status": self.status,
                "error": self.error, "counts": self.counts,
                "total": sum(self.counts.values()), "updated_at": self.updated_at}

    def start(self, camera_id: str, stream_url: str):
        with self._lock:
            if self._thread and self._thread.is_alive() and self.camera_id == camera_id:
                return self.snapshot()
            self._stop.set()
            old_thread = self._thread
        if old_thread and old_thread.is_alive():
            old_thread.join(timeout=3)
        with self._lock:
            self._stop = threading.Event()
            self.camera_id, self.status, self.error = camera_id, "connecting", None
            self.annotated_frame = None
            self._thread = threading.Thread(
                target=self._run, args=(camera_id, stream_url, self._stop), daemon=True,
                name=f"camera-inference-{camera_id}")
            self._thread.start()
            return self.snapshot()

    def stop(self, camera_id: str | None = None):
        with self._lock:
            if camera_id and camera_id != self.camera_id:
                return self.snapshot()
            self._stop.set()
            self.status = "stopped"
            return self.snapshot()

    def _run(self, camera_id: str, stream_url: str, stop: threading.Event):
        capture = None
        try:
            import cv2
            from ultralytics import YOLO

            model_path = Path(__file__).resolve().parents[3] / "yolo11m.pt"
            if not model_path.is_file():
                raise FileNotFoundError(f"YOLO model weights not found: {model_path}")
            model = YOLO(str(model_path))
            capture = cv2.VideoCapture(stream_url)
            last_ingest = 0.0
            while not stop.is_set():
                if not capture.isOpened():
                    capture.release()
                    time.sleep(1)
                    capture = cv2.VideoCapture(stream_url)
                    continue
                ok, frame = capture.read()
                if not ok or frame is None:
                    capture.release()
                    time.sleep(1)
                    capture = cv2.VideoCapture(stream_url)
                    continue
                prediction = model.predict(frame, conf=0.15, imgsz=640,
                                           classes=[2, 3, 5, 7], verbose=False)[0]
                class_ids = prediction.boxes.cls.cpu().numpy().astype(int) if prediction.boxes is not None else []
                annotated = prediction.plot()
                encoded, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                counts = {"cars": int((class_ids == 2).sum()),
                          "motorcycles": int((class_ids == 3).sum()),
                          "buses": int((class_ids == 5).sum()),
                          "trucks": int((class_ids == 7).sum())}
                with self._lock:
                    if self.camera_id == camera_id:
                        self.status, self.counts = "live", counts
                        self.updated_at = datetime.now(timezone.utc).isoformat()
                        if encoded:
                            self.annotated_frame = jpeg.tobytes()
                # Persist at most one frame count every 30 seconds.
                if time.monotonic() - last_ingest >= 30:
                    db = SessionLocal()
                    try:
                        TrafficModelAdapter.ingest_detection(db, DetectionIngestion(
                            camera_id=camera_id, timestamp=datetime.now(timezone.utc),
                            total=sum(counts.values()), **counts))
                    finally:
                        db.close()
                    last_ingest = time.monotonic()
        except Exception as error:
            with self._lock:
                if self.camera_id == camera_id:
                    self.status, self.error = "error", str(error)
        finally:
            if capture is not None:
                capture.release()
            with self._lock:
                if self.camera_id == camera_id and self.status != "error":
                    self.status = "stopped"


camera_inference = CameraInference()

"""Monitor current vehicle occupancy inside a camera-specific road polygon."""

import argparse
import csv
from collections import deque
from datetime import datetime, timezone
import json
import math
import re
import signal
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


# Edit these pixel coordinates to outline the road area in your camera view.
ROI_POLYGON = [(100, 200), (1100, 200), (1200, 700), (50, 700)]
ALERT_TOTAL_VEHICLES = 15
ALERT_COOLDOWN_SECONDS = 30.0
CSV_INTERVAL_SECONDS = 1.0
DEFAULT_SOURCE = (
    "https://gjirafa-video-live.gjirafa.net/gjvideo-slow/"
    "jrl-15u-0vp-6r8/tracks-v1a1/mono.ts.m3u8"
)
DEFAULT_RECONNECT_ATTEMPTS = 5
DEFAULT_RECONNECT_WAIT_SECONDS = 3.0
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
MODEL_PATH = Path(__file__).resolve().parent / "yolo11n.pt"
DEFAULT_MODEL = str(MODEL_PATH) if MODEL_PATH.is_file() else MODEL_PATH.name
RESULTS_DIR = Path(__file__).resolve().parent / "results"
STOP_REQUESTED = False

cv2: Any = None


def parse_polygon(value: str) -> tuple[tuple[int, int], ...]:
    """Parse a polygon supplied as comma-separated x,y pixel coordinates."""
    try:
        coordinates = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "ROI must be comma-separated x,y integer coordinate pairs"
        ) from error
    if len(coordinates) < 6 or len(coordinates) % 2:
        raise argparse.ArgumentTypeError(
            "ROI needs at least three x,y coordinate pairs"
        )
    if any(value < 0 for value in coordinates):
        raise argparse.ArgumentTypeError("ROI coordinates cannot be negative")
    return tuple(
        (coordinates[index], coordinates[index + 1])
        for index in range(0, len(coordinates), 2)
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count currently visible vehicles inside a polygon road area."
    )
    parser.add_argument("source", nargs="?", default=DEFAULT_SOURCE)
    parser.add_argument("camera_name", nargs="?", default=None)
    parser.add_argument("--camera", dest="camera_option", default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--tracker", default="bytetrack.yaml")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "0"),
        default="auto",
        help="Use CUDA GPU 0 when available, otherwise CPU",
    )
    parser.add_argument(
        "--roi",
        type=parse_polygon,
        default=tuple(ROI_POLYGON),
        metavar="X1,Y1,X2,Y2,X3,Y3,...",
        help="Polygon ROI in frame pixels; default is ROI_POLYGON in this file",
    )
    parser.add_argument(
        "--threshold",
        "--alert-total-vehicles",
        dest="threshold",
        type=int,
        default=ALERT_TOTAL_VEHICLES,
        help="Current in-ROI vehicle count that activates congestion alert",
    )
    parser.add_argument(
        "--alert-cooldown",
        type=float,
        default=ALERT_COOLDOWN_SECONDS,
        help="Seconds before an active alert can be logged again",
    )
    parser.add_argument(
        "--csv-interval",
        type=float,
        default=CSV_INTERVAL_SECONDS,
        help="Seconds between live_counts.csv snapshots",
    )
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument(
        "--reconnect-attempts", type=int, default=DEFAULT_RECONNECT_ATTEMPTS
    )
    parser.add_argument(
        "--reconnect-wait", type=float, default=DEFAULT_RECONNECT_WAIT_SECONDS
    )
    parser.add_argument("--show", action="store_true", help="Show preview; press q to stop")
    args = parser.parse_args(argv)

    if args.camera_name and args.camera_option:
        parser.error("give camera name positionally or with --camera, not both")
    args.camera_name = args.camera_name or args.camera_option or "gjirafa_cam"
    parsed_source = urlparse(args.source)
    args.is_stream = parsed_source.scheme.lower() in ("http", "https")
    if args.is_stream:
        if not parsed_source.path.lower().endswith(".m3u8"):
            parser.error("network source must be an HTTP(S) .m3u8 URL")
    else:
        is_windows_drive_path = bool(re.match(r"^[A-Za-z]:[\\/]", args.source))
        if parsed_source.scheme and not is_windows_drive_path:
            parser.error("source must be a local .mp4 path or HTTP(S) .m3u8 URL")
        if Path(args.source).suffix.lower() != ".mp4":
            parser.error("local source must be an .mp4 file")
        if not Path(args.source).is_file():
            parser.error(f"local video does not exist: {args.source}")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.camera_name):
        parser.error("camera name may contain only letters, numbers, underscores, and hyphens")
    if args.imgsz <= 0:
        parser.error("--imgsz must be greater than zero")
    if not 0.0 < args.conf <= 1.0:
        parser.error("--conf must be greater than 0 and at most 1")
    if args.threshold < 1:
        parser.error("--threshold must be at least 1")
    if args.alert_cooldown <= 0 or args.csv_interval <= 0:
        parser.error("alert cooldown and CSV interval must be greater than zero")
    if args.reconnect_attempts < 1 or args.reconnect_wait < 0:
        parser.error("reconnect attempts must be positive and wait cannot be negative")
    args.roi = tuple(args.roi)
    return args


def point_in_polygon(
    point: tuple[float, float], polygon: tuple[tuple[int, int], ...]
) -> bool:
    """Return whether a point is in or on the edge of a polygon."""
    point_x, point_y = point
    inside = False
    previous_x, previous_y = polygon[-1]
    for current_x, current_y in polygon:
        cross = (point_x - previous_x) * (current_y - previous_y) - (
            point_y - previous_y
        ) * (current_x - previous_x)
        if (
            abs(cross) < 1e-9
            and min(previous_x, current_x) <= point_x <= max(previous_x, current_x)
            and min(previous_y, current_y) <= point_y <= max(previous_y, current_y)
        ):
            return True
        if (current_y > point_y) != (previous_y > point_y):
            intersection_x = (previous_x - current_x) * (point_y - current_y) / (
                previous_y - current_y
            ) + current_x
            if point_x < intersection_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def evaluate_tracks(track_rows, roi_polygon):
    """Build this-frame visible tracks, in-ROI IDs, and class occupancy counts."""
    evaluated_rows = []
    current_tracks = {}
    current_counts = {name: 0 for name in VEHICLE_CLASSES.values()}
    for tracker_id, vehicle_class, confidence, box in track_rows:
        x1, y1, x2, y2 = (float(value) for value in box)
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        inside_roi = point_in_polygon((center_x, center_y), roi_polygon)
        row = {
            "tracker_id": tracker_id,
            "vehicle_class": vehicle_class,
            "confidence": float(confidence),
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "center_x": center_x,
            "center_y": center_y,
            "inside_roi": inside_roi,
        }
        evaluated_rows.append(row)
        if tracker_id is not None and inside_roi and tracker_id not in current_tracks:
            current_tracks[tracker_id] = row
            current_counts[vehicle_class] += 1
    return evaluated_rows, current_tracks, current_counts


def update_alert_state(current_total, threshold, alert_active, last_alert_time, now, cooldown):
    if current_total < threshold:
        if alert_active:
            return False, "ALERT_CLEARED", last_alert_time
        return False, None, last_alert_time
    if not alert_active:
        return True, "ALERT_STARTED", now
    if now - last_alert_time >= cooldown:
        return True, "ALERT_REMINDER", now
    return True, None, last_alert_time


def make_run_directory(output_root: Path, camera_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / f"{camera_name}_{timestamp}"
    suffix = 1
    while run_dir.exists():
        run_dir = output_root / f"{camera_name}_{timestamp}_{suffix:02d}"
        suffix += 1
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def get_device(requested: str) -> str:
    if requested != "auto":
        return requested
    import torch

    return "0" if torch.cuda.is_available() else "cpu"


def open_capture(source: str):
    if source.lower().startswith(("http://", "https://")):
        capture = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        if capture.isOpened():
            return capture
        capture.release()
    return cv2.VideoCapture(source)


def open_stream(source: str, attempts: int, wait_seconds: float):
    last_failure = "OpenCV could not open the stream"
    for attempt in range(1, attempts + 1):
        capture = open_capture(source)
        if capture.isOpened():
            success, frame = capture.read()
            if success and frame is not None:
                if attempt > 1:
                    print("Stream reconnected.", flush=True)
                return capture, frame
            last_failure = "stream opened, but OpenCV returned no frame"
        capture.release()
        print(
            f"Stream attempt {attempt}/{attempts} failed: {last_failure}",
            file=sys.stderr,
            flush=True,
        )
        if attempt < attempts:
            time.sleep(wait_seconds)
    raise RuntimeError(
        f"Unable to read the HLS stream after {attempts} attempts: {last_failure}. "
        "Check the URL/network and verify OpenCV has FFmpeg support."
    )


def draw_vehicle_label(frame, box, label, color):
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = [int(round(value)) for value in box]
    x1, x2 = max(0, min(x1, width - 1)), max(0, min(x2, width - 1))
    y1, y2 = max(0, min(y1, height - 1)), max(0, min(y2, height - 1))
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.48
    (label_width, label_height), baseline = cv2.getTextSize(label, font, scale, 1)
    label_top = max(0, y1 - label_height - baseline - 6)
    cv2.rectangle(
        frame,
        (x1, label_top),
        (min(width - 1, x1 + label_width + 8), y1),
        color,
        -1,
    )
    cv2.putText(
        frame,
        label,
        (x1 + 4, max(label_height, y1 - baseline - 3)),
        font,
        scale,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )


def draw_dashboard(frame, counts, total, alert_active, threshold, frame_number, fps, polygon):
    import numpy as np

    cv2.polylines(
        frame,
        [np.asarray(polygon, dtype="int32").reshape((-1, 1, 2))],
        True,
        (0, 220, 255),
        2,
    )
    background = (0, 0, 170) if alert_active else (28, 34, 38)
    cv2.rectangle(frame, (0, 0), (frame.shape[1] - 1, 65), background, -1)
    first_line = (
        f"Cars {counts['car']}  Motorcycles {counts['motorcycle']}  "
        f"Buses {counts['bus']}  Trucks {counts['truck']}  Total {total}"
    )
    status = "CONGESTION ALERT" if alert_active else "NORMAL"
    second_line = (
        f"{status} | Threshold {threshold} | Frame {frame_number} | FPS {fps:.1f}"
    )
    cv2.putText(
        frame,
        first_line,
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        second_line,
        (10, 53),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    if alert_active:
        banner_text = f"CONGESTION ALERT: {total} VEHICLES IN AREA"
        text_width = cv2.getTextSize(
            banner_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2
        )[0][0]
        banner_top = min(75, frame.shape[0] - 1)
        banner_bottom = min(banner_top + 42, frame.shape[0] - 1)
        cv2.rectangle(
            frame,
            (0, banner_top),
            (frame.shape[1] - 1, banner_bottom),
            (0, 0, 220),
            -1,
        )
        cv2.putText(
            frame,
            banner_text,
            (max(8, (frame.shape[1] - text_width) // 2), min(banner_bottom - 8, frame.shape[0] - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )


def write_live_count(writer, file_handle, timestamp, frame_number, counts, total, active, threshold):
    writer.writerow(
        [
            timestamp,
            frame_number,
            counts["car"],
            counts["motorcycle"],
            counts["bus"],
            counts["truck"],
            total,
            active,
            threshold,
        ]
    )
    file_handle.flush()


def process(args: argparse.Namespace) -> int:
    global cv2, STOP_REQUESTED
    import cv2 as opencv
    from ultralytics import YOLO

    cv2 = opencv
    STOP_REQUESTED = False

    def request_stop(_signal_number, _frame):
        global STOP_REQUESTED
        STOP_REQUESTED = True
        print("Stop requested; finishing the current frame...", flush=True)

    device = get_device(args.device)
    print(f"Using inference device: {'CUDA GPU 0' if device == '0' else 'CPU'}")
    print(f"Loading model: {args.model}")
    model = YOLO(args.model)

    run_dir = make_run_directory(args.output_dir, args.camera_name)
    annotated_path = run_dir / "annotated.mp4"
    live_counts_path = run_dir / "live_counts.csv"
    vehicle_tracks_path = run_dir / "vehicle_tracks.csv"
    alerts_path = run_dir / "alerts.csv"
    summary_path = run_dir / "summary.json"
    output_paths = {
        "annotated_video": str(annotated_path.resolve()),
        "live_counts_csv": str(live_counts_path.resolve()),
        "vehicle_tracks_csv": str(vehicle_tracks_path.resolve()),
        "alerts_csv": str(alerts_path.resolve()),
        "summary_json": str(summary_path.resolve()),
    }

    capture = None
    video_writer = None
    live_file = None
    tracks_file = None
    alerts_file = None
    processed_frames = 0
    max_total = 0
    max_by_class = {name: 0 for name in VEHICLE_CLASSES.values()}
    alert_active = False
    alert_events_written = 0
    alert_episodes = 0
    last_alert_time = -math.inf
    start_datetime = datetime.now(timezone.utc)
    start_monotonic = time.monotonic()
    next_live_count_time = start_monotonic
    current_tracks = {}
    fps = 30.0
    previous_sigint_handler = signal.signal(signal.SIGINT, request_stop)

    try:
        live_file = live_counts_path.open("w", newline="", encoding="utf-8")
        live_writer = csv.writer(live_file)
        live_writer.writerow(
            [
                "timestamp",
                "frame_number",
                "cars_in_roi",
                "motorcycles_in_roi",
                "buses_in_roi",
                "trucks_in_roi",
                "total_vehicles_in_roi",
                "alert_active",
                "alert_threshold",
            ]
        )
        tracks_file = vehicle_tracks_path.open("w", newline="", encoding="utf-8")
        tracks_writer = csv.writer(tracks_file)
        tracks_writer.writerow(
            [
                "timestamp",
                "frame_number",
                "tracker_id",
                "vehicle_class",
                "confidence",
                "x1",
                "y1",
                "x2",
                "y2",
                "center_x",
                "center_y",
                "inside_roi",
            ]
        )
        alerts_file = alerts_path.open("w", newline="", encoding="utf-8")
        alerts_writer = csv.writer(alerts_file)
        alerts_writer.writerow(
            [
                "timestamp",
                "frame_number",
                "event_type",
                "current_vehicle_total",
                "threshold",
                "message",
            ]
        )
        for file_handle in (live_file, tracks_file, alerts_file):
            file_handle.flush()

        print(f"Saving run to: {run_dir}")
        if args.is_stream:
            capture, frame = open_stream(
                args.source, args.reconnect_attempts, args.reconnect_wait
            )
        else:
            capture = open_capture(args.source)
            if not capture.isOpened():
                raise RuntimeError(f"Could not open local video file: {args.source}")
            success, frame = capture.read()
            if not success or frame is None:
                raise RuntimeError(f"Local video returned no first frame: {args.source}")

        frame_height, frame_width = frame.shape[:2]
        if any(x >= frame_width or y >= frame_height for x, y in args.roi):
            raise ValueError(
                f"ROI points must fit the video frame ({frame_width}x{frame_height}); "
                "edit ROI_POLYGON or pass --roi"
            )
        reported_fps = capture.get(cv2.CAP_PROP_FPS)
        if math.isfinite(reported_fps) and reported_fps > 0:
            fps = reported_fps
        video_writer = cv2.VideoWriter(
            str(annotated_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (frame_width, frame_height),
        )
        if not video_writer.isOpened():
            raise RuntimeError(f"Could not create annotated MP4: {annotated_path}")

        print(
            f"Counting current vehicle centers inside ROI {args.roi}; "
            f"congestion threshold is {args.threshold} vehicles."
        )
        while True:
            if STOP_REQUESTED:
                break
            frame_number = processed_frames + 1
            results = model.track(
                source=frame,
                persist=True,
                tracker=args.tracker,
                classes=list(VEHICLE_CLASSES),
                conf=args.conf,
                imgsz=args.imgsz,
                device=device,
                verbose=False,
            )
            result = results[0]
            boxes = result.boxes
            raw_tracks = []
            if boxes is not None and len(boxes):
                coordinates = boxes.xyxy.cpu().numpy()
                class_ids = boxes.cls.int().cpu().tolist()
                confidences = boxes.conf.cpu().tolist()
                tracker_ids = (
                    boxes.id.int().cpu().tolist()
                    if boxes.id is not None
                    else [None] * len(boxes)
                )
                for box, class_id, confidence, tracker_id in zip(
                    coordinates, class_ids, confidences, tracker_ids
                ):
                    vehicle_class = VEHICLE_CLASSES.get(int(class_id))
                    if vehicle_class is not None:
                        raw_tracks.append(
                            (
                                int(tracker_id) if tracker_id is not None else None,
                                vehicle_class,
                                float(confidence),
                                box,
                            )
                        )

            evaluated_rows, current_tracks, counts = evaluate_tracks(raw_tracks, args.roi)
            total = len(current_tracks)
            now_monotonic = time.monotonic()
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

            alert_active, alert_event, last_alert_time = update_alert_state(
                total,
                args.threshold,
                alert_active,
                last_alert_time,
                now_monotonic,
                args.alert_cooldown,
            )
            if alert_event is not None:
                if alert_event == "ALERT_STARTED":
                    alert_episodes += 1
                    message = (
                        f"Congestion risk - {total} vehicles currently in monitored area "
                        f"(threshold {args.threshold})."
                    )
                elif alert_event == "ALERT_REMINDER":
                    message = (
                        f"Congestion remains active - {total} vehicles currently in area."
                    )
                else:
                    message = (
                        f"Congestion alert cleared - {total} vehicles remain in monitored area."
                    )
                alerts_writer.writerow(
                    [timestamp, frame_number, alert_event, total, args.threshold, message]
                )
                alerts_file.flush()
                if alert_event != "ALERT_CLEARED":
                    alert_events_written += 1
                    print(f"ALERT: {message}", flush=True)

            max_total = max(max_total, total)
            for vehicle_class, count in counts.items():
                max_by_class[vehicle_class] = max(max_by_class[vehicle_class], count)

            annotated = frame.copy()
            import numpy as np

            cv2.polylines(
                annotated,
                [np.asarray(args.roi, dtype="int32").reshape((-1, 1, 2))],
                True,
                (0, 220, 255),
                2,
            )
            for row in evaluated_rows:
                tracker_id = row["tracker_id"]
                if not row["inside_roi"]:
                    color = (125, 125, 125)
                elif alert_active:
                    color = (0, 220, 255)
                else:
                    color = (0, 200, 0)
                identifier = f"#{tracker_id}" if tracker_id is not None else "#pending"
                draw_vehicle_label(
                    annotated,
                    (row["x1"], row["y1"], row["x2"], row["y2"]),
                    f"{row['vehicle_class']} {identifier} {row['confidence']:.2f}",
                    color,
                )
                if tracker_id is not None:
                    tracks_writer.writerow(
                        [
                            timestamp,
                            frame_number,
                            tracker_id,
                            row["vehicle_class"],
                            f"{row['confidence']:.5f}",
                            f"{row['x1']:.2f}",
                            f"{row['y1']:.2f}",
                            f"{row['x2']:.2f}",
                            f"{row['y2']:.2f}",
                            f"{row['center_x']:.2f}",
                            f"{row['center_y']:.2f}",
                            row["inside_roi"],
                        ]
                    )

            processed_frames = frame_number
            elapsed = max(now_monotonic - start_monotonic, 1e-6)
            processing_fps = processed_frames / elapsed
            draw_dashboard(
                annotated,
                counts,
                total,
                alert_active,
                args.threshold,
                frame_number,
                processing_fps,
                args.roi,
            )
            video_writer.write(annotated)

            if now_monotonic >= next_live_count_time:
                write_live_count(
                    live_writer,
                    live_file,
                    timestamp,
                    frame_number,
                    counts,
                    total,
                    alert_active,
                    args.threshold,
                )
                next_live_count_time = now_monotonic + args.csv_interval
            if frame_number % 100 == 0:
                tracks_file.flush()
                print(
                    f"Frame {frame_number}: {total} vehicles currently in area "
                    f"(cars {counts['car']}, motorcycles {counts['motorcycle']}, "
                    f"buses {counts['bus']}, trucks {counts['truck']}).",
                    flush=True,
                )
            if args.show:
                cv2.imshow(f"CityFlow - {args.camera_name}", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("Stop requested with q.", flush=True)
                    break

            success, next_frame = capture.read()
            if success and next_frame is not None:
                frame = next_frame
            elif not args.is_stream:
                break
            else:
                print("HLS frame read failed; reconnecting...", file=sys.stderr, flush=True)
                capture.release()
                capture, frame = open_stream(
                    args.source, args.reconnect_attempts, args.reconnect_wait
                )

        if processed_frames:
            final_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            final_counts = {name: 0 for name in VEHICLE_CLASSES.values()}
            for current_track in current_tracks.values():
                final_counts[current_track["vehicle_class"]] += 1
            write_live_count(
                live_writer,
                live_file,
                final_timestamp,
                processed_frames,
                final_counts,
                len(current_tracks),
                alert_active,
                args.threshold,
            )
        end_datetime = datetime.now(timezone.utc)
        summary = {
            "source": args.source,
            "camera_name": args.camera_name,
            "model": args.model,
            "tracker": args.tracker,
            "start_time": start_datetime.isoformat(timespec="seconds"),
            "end_time": end_datetime.isoformat(timespec="seconds"),
            "frames_processed": processed_frames,
            "maximum_concurrent_vehicles_in_roi": max_total,
            "maximum_cars_in_roi": max_by_class["car"],
            "maximum_motorcycles_in_roi": max_by_class["motorcycle"],
            "maximum_buses_in_roi": max_by_class["bus"],
            "maximum_trucks_in_roi": max_by_class["truck"],
            "alert_threshold": args.threshold,
            "number_of_alerts": alert_episodes,
            "number_of_alert_events": alert_events_written,
            "roi_polygon": args.roi,
            "device": device,
            "output_files": output_paths,
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Finished after {processed_frames} frames.")
        print(f"Run outputs: {run_dir}")
        return 0
    finally:
        if video_writer is not None:
            video_writer.release()
        if capture is not None:
            capture.release()
        if live_file is not None:
            live_file.close()
        if tracks_file is not None:
            tracks_file.close()
        if alerts_file is not None:
            alerts_file.close()
        signal.signal(signal.SIGINT, previous_sigint_handler)
        if args.show and cv2 is not None:
            cv2.destroyAllWindows()


def main(argv: list[str] | None = None) -> int:
    try:
        return process(parse_args(argv))
    except KeyboardInterrupt:
        print("Stopped by user.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
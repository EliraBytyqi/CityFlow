"""Track and count vehicles in a local video or an HLS camera stream."""

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


# Edit these defaults for a fixed camera installation, or override them on CLI.
DEFAULT_LINE_POSITION = 0.60
DEFAULT_ALERT_TOTAL_VEHICLES = 45
DEFAULT_ALERT_VEHICLES_PER_MINUTE = 45.0
DEFAULT_ALERT_COOLDOWN_SECONDS = 30.0
DEFAULT_RECONNECT_ATTEMPTS = 5
DEFAULT_RECONNECT_WAIT_SECONDS = 3.0
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
MODEL_PATH = Path(__file__).resolve().parent / "yolo11n.pt"
DEFAULT_MODEL = str(MODEL_PATH) if MODEL_PATH.is_file() else MODEL_PATH.name
RESULTS_DIR = Path(__file__).resolve().parent / "results"
STOP_REQUESTED = False

cv2: Any = None
YOLO: Any = None


def parse_polygon(value: str) -> tuple[tuple[int, int], ...]:
    """Parse at least three x,y pixel-coordinate pairs."""
    try:
        values = [int(part.strip()) for part in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "zone must be comma-separated x,y pixel coordinate pairs"
        ) from error
    if len(values) < 6 or len(values) % 2:
        raise argparse.ArgumentTypeError(
            "zone must contain at least three x,y coordinate pairs"
        )
    if any(value < 0 for value in values):
        raise argparse.ArgumentTypeError("zone coordinates cannot be negative")
    return tuple((values[index], values[index + 1]) for index in range(0, len(values), 2))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Track vehicles and save unique line-crossing or zone-entry events."
    )
    parser.add_argument(
        "source",
        nargs="?",
        default="https://gjirafa-video-live.gjirafa.net/gjvideo-slow/"
        "jrl-15u-0vp-6r8/tracks-v1a1/mono.ts.m3u8",
        help="Local video file or HTTP(S) HLS .m3u8 URL",
    )
    parser.add_argument("camera_positional", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("--camera", default=None, help="Camera/run name")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="YOLO model or weights path")
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO image size")
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "0"),
        default="auto",
        help="Inference device (default: use CUDA when available, otherwise CPU)",
    )
    counter_group = parser.add_mutually_exclusive_group()
    counter_group.add_argument(
        "--line-position",
        type=float,
        default=None,
        metavar="FRACTION",
        help="Horizontal line height from 0 to 1 (default: 0.60)",
    )
    counter_group.add_argument(
        "--zone",
        type=parse_polygon,
        metavar="X1,Y1,X2,Y2,X3,Y3,...",
        help="Polygon zone as pixel coordinate pairs; counts first entry only",
    )
    parser.add_argument(
        "--direction",
        choices=("any", "down", "up"),
        default="any",
        help="Accepted crossing direction for line mode (image coordinates)",
    )
    parser.add_argument(
        "--tracker",
        default="bytetrack.yaml",
        help="Ultralytics tracker configuration (default: bytetrack.yaml)",
    )
    parser.add_argument("--alert-total-vehicles", type=int, default=DEFAULT_ALERT_TOTAL_VEHICLES)
    parser.add_argument(
        "--alert-vehicles-per-minute",
        type=float,
        default=DEFAULT_ALERT_VEHICLES_PER_MINUTE,
    )
    parser.add_argument(
        "--alert-cooldown",
        type=float,
        default=DEFAULT_ALERT_COOLDOWN_SECONDS,
        help="Minimum seconds between repeated alert rows",
    )
    parser.add_argument(
        "--reconnect-attempts", type=int, default=DEFAULT_RECONNECT_ATTEMPTS
    )
    parser.add_argument(
        "--reconnect-wait",
        type=float,
        default=DEFAULT_RECONNECT_WAIT_SECONDS,
        help="Seconds between HLS reconnection attempts",
    )
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--show", action="store_true", help="Show live preview; press q to quit")
    args = parser.parse_args(argv)
    if args.camera is not None and args.camera_positional is not None:
        parser.error("use either positional camera or --camera, not both")
    args.camera = args.camera or args.camera_positional or "gjirafa_cam"

    parsed_source = urlparse(args.source)
    args.is_stream = parsed_source.scheme.lower() in ("http", "https")
    if args.is_stream and not parsed_source.path.lower().endswith(".m3u8"):
        parser.error("network source must be an HTTP(S) .m3u8 URL")
    if not args.is_stream:
        is_windows_drive_path = bool(re.match(r"^[A-Za-z]:[\\/]", args.source))
        if parsed_source.scheme and not is_windows_drive_path:
            parser.error("source must be a local video path or HTTP(S) .m3u8 URL")
        if not Path(args.source).is_file():
            parser.error(f"video file does not exist: {args.source}")
        if Path(args.source).suffix.lower() not in (".mp4", ".avi", ".mov", ".mkv"):
            parser.error("local source must be .mp4, .avi, .mov, or .mkv")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.camera):
        parser.error("--camera may contain only letters, digits, underscores, and hyphens")
    if args.imgsz <= 0:
        parser.error("--imgsz must be greater than zero")
    if args.line_position is not None and not 0.0 <= args.line_position <= 1.0:
        parser.error("--line-position must be between 0 and 1")
    if args.alert_total_vehicles < 0 or args.alert_vehicles_per_minute < 0:
        parser.error("alert thresholds cannot be negative")
    if args.alert_cooldown < 0 or args.reconnect_wait < 0:
        parser.error("cooldown and reconnect wait cannot be negative")
    if args.reconnect_attempts < 1:
        parser.error("--reconnect-attempts must be at least 1")
    args.counter_mode = "zone" if args.zone else "line"
    args.effective_line_position = (
        args.line_position
        if args.line_position is not None
        else DEFAULT_LINE_POSITION
    )
    return args


def crossing_direction(previous_y: float, current_y: float, line_y: float) -> str | None:
    """Return down/up only when the anchor point crosses the horizontal line."""
    previous_side = previous_y - line_y
    current_side = current_y - line_y
    if previous_side < 0 <= current_side:
        return "down"
    if previous_side > 0 >= current_side:
        return "up"
    return None


def inside_polygon(point: tuple[float, float], polygon: tuple[tuple[int, int], ...]) -> bool:
    """Ray-cast point-in-polygon helper, including points on polygon edges."""
    x, y = point
    inside = False
    previous_x, previous_y = polygon[-1]
    for current_x, current_y in polygon:
        cross = (x - previous_x) * (current_y - previous_y) - (
            y - previous_y
        ) * (current_x - previous_x)
        if abs(cross) < 1e-9 and min(previous_x, current_x) <= x <= max(
            previous_x, current_x
        ) and min(previous_y, current_y) <= y <= max(previous_y, current_y):
            return True
        if (current_y > y) != (previous_y > y):
            intersection_x = (previous_x - current_x) * (y - current_y) / (
                previous_y - current_y
            ) + current_x
            if x < intersection_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def make_run_directory(output_root: Path, camera: str, now: datetime | None = None) -> Path:
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / f"{camera}_{timestamp}"
    suffix = 1
    while run_dir.exists():
        run_dir = output_root / f"{camera}_{timestamp}_{suffix:02d}"
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


def open_stream_frame(source: str, attempts: int, wait_seconds: float):
    last_error = "no frame received"
    for attempt in range(1, attempts + 1):
        capture = open_capture(source)
        if capture.isOpened():
            success, frame = capture.read()
            if success and frame is not None:
                if attempt > 1:
                    print("Stream reconnected.", flush=True)
                return capture, frame
            last_error = "stream opened but returned no frame"
        else:
            last_error = "OpenCV could not open the source"
        capture.release()
        print(
            f"Stream open/read attempt {attempt}/{attempts} failed: {last_error}",
            file=sys.stderr,
            flush=True,
        )
        if attempt < attempts:
            time.sleep(wait_seconds)
    raise RuntimeError(
        f"Could not read from source after {attempts} attempts ({last_error}). "
        "Check the URL/network, or install a full OpenCV build with FFmpeg support."
    )


def draw_label(frame, box, text, color):
    x1, y1, x2, y2 = [int(round(value)) for value in box]
    height, width = frame.shape[:2]
    x1, x2 = max(0, min(x1, width - 1)), max(0, min(x2, width - 1))
    y1, y2 = max(0, min(y1, height - 1)), max(0, min(y2, height - 1))
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.5
    (label_width, label_height), baseline = cv2.getTextSize(text, font, scale, 1)
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
        text,
        (x1 + 4, max(label_height, y1 - baseline - 3)),
        font,
        scale,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )


def draw_overlay(frame, totals, unique_total, rate, alert_active, line_y, polygon):
    if polygon:
        import numpy as np

        cv2.polylines(
            frame,
            [np.asarray(polygon, dtype="int32").reshape((-1, 1, 2))],
            True,
            (0, 220, 255),
            2,
        )
    else:
        cv2.line(frame, (0, line_y), (frame.shape[1] - 1, line_y), (0, 220, 255), 2)
    banner_color = (0, 0, 170) if alert_active else (25, 25, 25)
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 78), banner_color, -1)
    status = "CONGESTION ALERT" if alert_active else "STATUS: NORMAL"
    status_color = (255, 255, 255) if alert_active else (0, 210, 0)
    cv2.putText(
        frame,
        f"Cars {totals['car']}  Motorcycles {totals['motorcycle']}  "
        f"Buses {totals['bus']}  Trucks {totals['truck']}  Total {unique_total}",
        (10, 27),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        f"Unique vehicles/min: {rate:.1f}   {status}",
        (10, 58),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        status_color,
        2,
        cv2.LINE_AA,
    )


def process(args: argparse.Namespace) -> int:
    global cv2, YOLO
    import cv2 as opencv
    from ultralytics import YOLO as yolo_class

    cv2 = opencv
    YOLO = yolo_class
    global STOP_REQUESTED
    STOP_REQUESTED = False

    def request_stop(_signum, _frame):
        global STOP_REQUESTED
        STOP_REQUESTED = True
        print("Stop requested; finishing the current frame...", flush=True)

    device = get_device(args.device)
    print(f"Using inference device: {'CUDA GPU 0' if device == '0' else 'CPU'}")
    print(f"Loading model: {args.model} (Ultralytics downloads named weights if needed)")
    model = YOLO(args.model)

    capture = None
    video_writer = None
    event_file = None
    alert_file = None
    run_dir = make_run_directory(args.output_dir, args.camera)
    events_path = run_dir / "vehicle_events.csv"
    alerts_path = run_dir / "alerts.csv"
    summary_path = run_dir / "summary.json"
    annotated_path = run_dir / "annotated.mp4"
    event_count = 0
    alert_count = 0
    processed_frames = 0
    unique_counted_ids: set[int] = set()
    totals = {name: 0 for name in VEHICLE_CLASSES.values()}
    previous_anchor: dict[int, tuple[float, float]] = {}
    seen_in_zone: set[int] = set()
    recent_events: deque[float] = deque()
    alert_active = False
    last_alert_time = -math.inf
    start_time = time.monotonic()
    fps = 30.0
    previous_sigint_handler = signal.signal(signal.SIGINT, request_stop)

    try:
        if args.is_stream:
            capture, frame = open_stream_frame(
                args.source, args.reconnect_attempts, args.reconnect_wait
            )
        else:
            capture = open_capture(args.source)
            if not capture.isOpened():
                raise RuntimeError(f"Could not open local video: {args.source}")
            success, frame = capture.read()
            if not success or frame is None:
                raise RuntimeError(f"Local video contains no readable frames: {args.source}")

        frame_height, frame_width = frame.shape[:2]
        reported_fps = capture.get(cv2.CAP_PROP_FPS)
        if math.isfinite(reported_fps) and reported_fps > 0:
            fps = reported_fps
        line_y = round((frame_height - 1) * args.effective_line_position)
        polygon = args.zone
        if polygon and any(x >= frame_width or y >= frame_height for x, y in polygon):
            raise ValueError(
                f"Zone coordinates must fit this video frame ({frame_width}x{frame_height})"
            )

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(
            str(annotated_path), fourcc, fps, (frame_width, frame_height)
        )
        if not video_writer.isOpened():
            raise RuntimeError(f"Could not create output video: {annotated_path}")

        event_file = events_path.open("w", newline="", encoding="utf-8")
        event_writer = csv.writer(event_file)
        event_writer.writerow(
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
                "event_type",
            ]
        )
        event_file.flush()
        alert_file = alerts_path.open("w", newline="", encoding="utf-8")
        alert_writer = csv.writer(alert_file)
        alert_writer.writerow(
            ["timestamp", "frame_number", "total_unique_vehicles", "vehicles_per_minute", "reason"]
        )
        alert_file.flush()

        print(f"Saving this run to: {run_dir}")
        print(
            "Counting first line crossing"
            if not polygon
            else f"Counting first entry to polygon zone: {polygon}"
        )

        while True:
            if STOP_REQUESTED:
                break
            results = model.track(
                source=frame,
                persist=True,
                tracker=args.tracker,
                classes=list(VEHICLE_CLASSES),
                imgsz=args.imgsz,
                device=device,
                verbose=False,
            )
            result = results[0]
            boxes = result.boxes
            annotated = frame.copy()
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

            if boxes is not None and len(boxes):
                xyxy = boxes.xyxy.cpu().numpy()
                class_ids = boxes.cls.int().cpu().tolist()
                confidences = boxes.conf.cpu().tolist()
                tracker_ids = (
                    boxes.id.int().cpu().tolist()
                    if boxes.id is not None
                    else [None] * len(boxes)
                )
                for box, class_id, confidence, tracker_id in zip(
                    xyxy, class_ids, confidences, tracker_ids
                ):
                    class_name = VEHICLE_CLASSES.get(int(class_id))
                    if class_name is None:
                        continue
                    coordinates = [float(value) for value in box]
                    x1, y1, x2, y2 = coordinates
                    anchor = ((x1 + x2) / 2.0, y2)
                    event_type = "detection"
                    should_count = False

                    if tracker_id is not None:
                        tracker_id = int(tracker_id)
                        if polygon:
                            inside_now = inside_polygon(anchor, polygon)
                            if inside_now and tracker_id not in seen_in_zone:
                                event_type = "zone_entry"
                                should_count = True
                            if inside_now:
                                seen_in_zone.add(tracker_id)
                        else:
                            previous = previous_anchor.get(tracker_id)
                            if previous is not None:
                                crossing = crossing_direction(previous[1], anchor[1], line_y)
                                if crossing is not None:
                                    event_type = f"line_crossing_{crossing}"
                                    should_count = args.direction == "any" or args.direction == crossing
                            previous_anchor[tracker_id] = anchor

                        if should_count and tracker_id not in unique_counted_ids:
                            unique_counted_ids.add(tracker_id)
                            totals[class_name] += 1
                            recent_events.append(time.monotonic())
                        elif should_count:
                            event_type = "duplicate_crossing_ignored"

                    event_writer.writerow(
                        [
                            timestamp,
                            processed_frames + 1,
                            tracker_id if tracker_id is not None else "",
                            class_name,
                            f"{float(confidence):.5f}",
                            *[f"{value:.2f}" for value in coordinates],
                            event_type,
                        ]
                    )
                    event_count += 1
                    color = (40, 210, 40) if event_type != "zone_entry" and not event_type.startswith("line_crossing") else (0, 220, 255)
                    label_id = f" #{tracker_id}" if tracker_id is not None else " #pending"
                    draw_label(
                        annotated,
                        coordinates,
                        f"{class_name}{label_id} {float(confidence):.2f}",
                        color,
                    )

            now_monotonic = time.monotonic()
            while recent_events and now_monotonic - recent_events[0] > 60.0:
                recent_events.popleft()
            vehicles_per_minute = len(recent_events)
            total_unique = len(unique_counted_ids)
            reasons = []
            if args.alert_total_vehicles > 0 and total_unique >= args.alert_total_vehicles:
                reasons.append(f"total unique vehicles >= {args.alert_total_vehicles}")
            if (
                args.alert_vehicles_per_minute > 0
                and vehicles_per_minute >= args.alert_vehicles_per_minute
            ):
                reasons.append(
                    f"vehicles/minute >= {args.alert_vehicles_per_minute:g}"
                )
            threshold_active = bool(reasons)
            if not threshold_active:
                alert_active = False
            elif not alert_active or now_monotonic - last_alert_time >= args.alert_cooldown:
                reason = "; ".join(reasons)
                alert_writer.writerow(
                    [timestamp, processed_frames + 1, total_unique, vehicles_per_minute, reason]
                )
                alert_file.flush()
                alert_count += 1
                last_alert_time = now_monotonic
                alert_active = True
                print(
                    f"ALERT: Congestion risk - {total_unique} unique vehicles counted "
                    f"({vehicles_per_minute}/min; {reason})",
                    flush=True,
                )
            else:
                alert_active = True

            draw_overlay(
                annotated,
                totals,
                total_unique,
                vehicles_per_minute,
                alert_active,
                line_y,
                polygon,
            )
            video_writer.write(annotated)
            processed_frames += 1
            if processed_frames % 100 == 0:
                event_file.flush()
                elapsed = max(time.monotonic() - start_time, 1.0)
                print(
                    f"Frames: {processed_frames}; unique counted: {total_unique}; "
                    f"rate: {vehicles_per_minute}/min; processing: "
                    f"{processed_frames / elapsed:.1f} FPS",
                    flush=True,
                )
            if args.show:
                cv2.imshow(f"CityFlow - {args.camera}", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("Stop requested with q.", flush=True)
                    break

            success, next_frame = capture.read()
            if success and next_frame is not None:
                frame = next_frame
                continue
            if not args.is_stream:
                break
            capture.release()
            capture, frame = open_stream_frame(
                args.source, args.reconnect_attempts, args.reconnect_wait
            )

        elapsed_seconds = max(time.monotonic() - start_time, 0.0)
        summary = {
            "camera": args.camera,
            "source": args.source,
            "started_at_utc": datetime.fromtimestamp(
                time.time() - elapsed_seconds, timezone.utc
            ).isoformat(timespec="seconds"),
            "finished_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "processed_frames": processed_frames,
            "elapsed_seconds": round(elapsed_seconds, 2),
            "counting_mode": args.counter_mode,
            "line_position_fraction": None if polygon else args.effective_line_position,
            "line_direction": args.direction if not polygon else None,
            "zone_polygon_pixels": polygon,
            "unique_vehicles_counted": len(unique_counted_ids),
            "totals_by_vehicle_class": totals,
            "vehicle_event_rows": event_count,
            "alerts_written": alert_count,
            "alert_threshold_total_vehicles": args.alert_total_vehicles,
            "alert_threshold_vehicles_per_minute": args.alert_vehicles_per_minute,
            "model": args.model,
            "tracker": args.tracker,
            "device": device,
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Finished. Processed {processed_frames} frames.")
        print(f"Summary: {summary_path}")
        print(f"Events: {events_path}")
        print(f"Alerts: {alerts_path}")
        print(f"Annotated video: {annotated_path}")
        return 0
    finally:
        if video_writer is not None:
            video_writer.release()
        if capture is not None:
            capture.release()
        if event_file is not None:
            event_file.close()
        if alert_file is not None:
            alert_file.close()
        signal.signal(signal.SIGINT, previous_sigint_handler)
        if args.show and cv2 is not None:
            cv2.destroyAllWindows()


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        return process(args)
    except KeyboardInterrupt:
        print("Stopped by user.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
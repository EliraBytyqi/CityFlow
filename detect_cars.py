# Usage examples:
# Occupancy:           python detect_cars.py SRC CAM --alert-at 8
# Cropped road ROI:    python detect_cars.py SRC CAM --crop 250,720,0,1280 --roi 0,500,1280,500,1280,720,0,720
import argparse
import csv
from collections import deque
from datetime import datetime
import importlib
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any
from urllib.parse import urlparse


cv2: Any = None
sv: Any = None
YOLO: Any = None
np: Any = None
VEHICLE_CLASSES = (2, 3, 5, 7)
CLASS_NAMES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}
CSV_FLUSH_SECONDS = 60
STREAM_RETRIES = 5
STREAM_RETRY_WAIT_SECONDS = 10
MODEL_PATH = Path(__file__).resolve().parent / "yolo11m.pt"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Detect, track, and count vehicles in an MP4 or HLS stream."
    )
    parser.add_argument("source", help="HLS .m3u8 URL or local .mp4 file")
    parser.add_argument("camera", help="Camera name for output filenames and CSV")
    parser.add_argument(
        "--imgsz",
        type=int,
        default=1280,
        help="YOLO inference image size (default: 1280)",
    )
    parser.add_argument(
        "--crop",
        type=parse_crop,
        default=None,
        metavar="TOP,BOTTOM,LEFT,RIGHT",
        help="Crop bounds in pixels; omitted means full frame",
    )
    parser.add_argument(
        "--roi",
        type=parse_roi,
        default=None,
        metavar="X1,Y1,X2,Y2,X3,Y3,X4,Y4",
        help="Road-region quadrilateral in original-frame pixels",
    )
    parser.add_argument(
        "--alert-at",
        type=int,
        default=8,
        metavar="N",
        help="Vehicle occupancy that triggers a congestion alert (default: 8)",
    )
    parser.add_argument(
        "--park-seconds",
        type=float,
        default=15.0,
        help="Motion-history window in seconds for parked classification (default: 15)",
    )
    parser.add_argument(
        "--hide-parked",
        action="store_true",
        help="Do not draw parked vehicle boxes",
    )
    args = parser.parse_args()

    parsed_source = urlparse(args.source)
    args.is_stream = (
        parsed_source.scheme.lower() in ("http", "https")
        and parsed_source.path.lower().endswith(".m3u8")
    )
    if not args.is_stream:
        if Path(args.source).suffix.lower() != ".mp4":
            parser.error("source must be a local .mp4 path or an HTTP(S) .m3u8 URL")
        if not Path(args.source).is_file():
            parser.error(f"video file does not exist: {args.source}")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.camera):
        parser.error("camera must contain only letters, numbers, underscores, or hyphens")
    if args.imgsz <= 0:
        parser.error("--imgsz must be greater than zero")
    if args.alert_at <= 0:
        parser.error("--alert-at must be greater than zero")
    if args.park_seconds <= 0:
        parser.error("--park-seconds must be greater than zero")
    return args


def parse_crop(value):
    try:
        bounds = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "crop must contain four comma-separated integer pixel values"
        ) from error
    if len(bounds) != 4:
        raise argparse.ArgumentTypeError(
            "crop must use the format top,bottom,left,right"
        )
    if any(bound < 0 for bound in bounds):
        raise argparse.ArgumentTypeError("crop coordinates cannot be negative")
    top, bottom, left, right = bounds
    if bottom <= top or right <= left:
        raise argparse.ArgumentTypeError(
            "crop bottom must exceed top and right must exceed left"
        )
    return bounds


def parse_roi(value):
    try:
        coordinates = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "ROI must contain eight comma-separated integers: x1,y1,...,x4,y4"
        ) from error
    if len(coordinates) != 8:
        raise argparse.ArgumentTypeError(
            "ROI must contain eight comma-separated integers: x1,y1,...,x4,y4"
        )
    if any(coordinate < 0 for coordinate in coordinates):
        raise argparse.ArgumentTypeError("ROI coordinates cannot be negative")
    return coordinates


def validate_crop(crop, frame_height, frame_width):
    if crop is None:
        return 0, frame_height, 0, frame_width
    top, bottom, left, right = crop
    if bottom > frame_height or right > frame_width:
        raise ValueError(
            f"Crop {crop} exceeds frame dimensions {frame_height}x{frame_width}"
        )
    return crop


def validate_roi(roi, frame_height, frame_width):
    if roi is None:
        return None
    points = np.asarray(roi, dtype=np.int32).reshape((4, 2))
    if (
        np.any(points[:, 0] >= frame_width)
        or np.any(points[:, 1] >= frame_height)
    ):
        raise ValueError(
            f"ROI coordinates exceed frame dimensions {frame_height}x{frame_width}"
        )
    return points.reshape((-1, 1, 2))


def restore_detection_coordinates(detections, crop_left, crop_top):
    if crop_left == 0 and crop_top == 0:
        return detections
    return sv.Detections(
        xyxy=detections.xyxy
        + np.asarray([crop_left, crop_top, crop_left, crop_top], dtype=np.float32),
        confidence=detections.confidence,
        class_id=detections.class_id,
        data=detections.data,
    )


def tracked_detections_in_roi(detections, roi_contour):
    if detections.tracker_id is None or len(detections) == 0:
        return detections[:0]

    tracked_mask = np.asarray(
        [
            tracker_id is not None and int(tracker_id) >= 0
            for tracker_id in detections.tracker_id
        ],
        dtype=bool,
    )
    if roi_contour is None:
        return detections[tracked_mask]

    in_roi_mask = np.zeros(len(detections), dtype=bool)
    for index, box in enumerate(detections.xyxy):
        if not tracked_mask[index]:
            continue
        anchor = ((float(box[0]) + float(box[2])) / 2.0, float(box[3]))
        in_roi_mask[index] = cv2.pointPolygonTest(roi_contour, anchor, False) >= 0
    return detections[in_roi_mask]


def update_motion_classification(
    detections,
    frame_number,
    histories,
    last_seen,
    states,
    parked_spots,
    spot_parked_ids,
    fps,
    park_seconds,
):
    window_length = max(2, int(round(fps * park_seconds)))
    centers = []
    current_states = {}

    if detections.tracker_id is not None:
        for index, tracker_id_value in enumerate(detections.tracker_id):
            if tracker_id_value is None or int(tracker_id_value) < 0:
                continue
            tracker_id = int(tracker_id_value)
            x1, y1, x2, y2 = detections.xyxy[index]
            center_x = (float(x1) + float(x2)) / 2.0
            center_y = (float(y1) + float(y2)) / 2.0
            centers.append((center_x, center_y))

            history = histories.get(tracker_id)
            is_new_id = history is None
            if is_new_id:
                history = deque(maxlen=window_length)
                histories[tracker_id] = history
            history.append((center_x, center_y))
            last_seen[tracker_id] = frame_number

            linked_spot = spot_parked_ids.get(tracker_id)
            if linked_spot not in parked_spots:
                linked_spot = None
                spot_parked_ids.pop(tracker_id, None)
            if is_new_id:
                linked_spot = next(
                    (
                        spot
                        for spot in parked_spots
                        if math.hypot(
                            center_x - spot["cx"], center_y - spot["cy"]
                        )
                        <= 40
                    ),
                    None,
                )
                if linked_spot is not None:
                    spot_parked_ids[tracker_id] = linked_spot

            near_parked_spot = (
                linked_spot is not None
                and math.hypot(
                    center_x - linked_spot["cx"], center_y - linked_spot["cy"]
                )
                <= 40
            )
            if near_parked_spot:
                state = "PARKED"
            else:
                spot_parked_ids.pop(tracker_id, None)
                x_values = [sample[0] for sample in history]
                y_values = [sample[1] for sample in history]
                history_is_full = len(history) == history.maxlen
                drift_range = max(
                    max(x_values) - min(x_values),
                    max(y_values) - min(y_values),
                )
                state = (
                    "PARKED"
                    if history_is_full and drift_range <= 12
                    else "MOVING"
                )

            if state == "PARKED" and not any(
                math.hypot(center_x - spot["cx"], center_y - spot["cy"]) <= 40
                for spot in parked_spots
            ):
                parked_spots.append(
                    {
                        "cx": center_x,
                        "cy": center_y,
                        "last_seen_frame": frame_number,
                    }
                )
            states[tracker_id] = state
            current_states[tracker_id] = state

    for spot in parked_spots:
        if any(
            math.hypot(center_x - spot["cx"], center_y - spot["cy"]) <= 80
            for center_x, center_y in centers
        ):
            spot["last_seen_frame"] = frame_number
    parked_spots[:] = [
        spot
        for spot in parked_spots
        if frame_number - spot["last_seen_frame"] < 60
    ]

    stale_ids = [
        tracker_id
        for tracker_id, last_frame in last_seen.items()
        if frame_number - last_frame >= 60
    ]
    for tracker_id in stale_ids:
        histories.pop(tracker_id, None)
        last_seen.pop(tracker_id, None)
        states.pop(tracker_id, None)
        spot_parked_ids.pop(tracker_id, None)

    return current_states


def reconnect_stream(source, current_capture):
    if current_capture is not None:
        current_capture.release()

    for attempt in range(1, STREAM_RETRIES + 1):
        print(
            f"Stream read failed; reconnect attempt {attempt}/{STREAM_RETRIES} "
            f"in {STREAM_RETRY_WAIT_SECONDS} seconds...",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(STREAM_RETRY_WAIT_SECONDS)
        candidate = cv2.VideoCapture(source)
        if candidate.isOpened():
            success, frame = candidate.read()
            if success and frame is not None:
                print("Stream reconnected.", flush=True)
                return candidate, frame
        candidate.release()

    raise RuntimeError(
        f"Unable to read a frame from stream after {STREAM_RETRIES} retries: {source}"
    )


def associate_tracker_ids(detections, tracked_detections):
    assigned_ids = np.full(len(detections), -1, dtype=np.int64)
    if (
        detections.class_id is None
        or tracked_detections.class_id is None
        or tracked_detections.tracker_id is None
    ):
        return assigned_ids

    available_indices = set(range(len(detections)))
    for tracked_index, tracked_box in enumerate(tracked_detections.xyxy):
        tracker_id = int(tracked_detections.tracker_id[tracked_index])
        tracked_class = tracked_detections.class_id[tracked_index]
        candidates = [
            index
            for index in available_indices
            if detections.class_id[index] == tracked_class
        ]
        if not candidates:
            continue

        boxes = detections.xyxy[candidates]
        left = np.maximum(boxes[:, 0], tracked_box[0])
        top = np.maximum(boxes[:, 1], tracked_box[1])
        right = np.minimum(boxes[:, 2], tracked_box[2])
        bottom = np.minimum(boxes[:, 3], tracked_box[3])
        intersection = np.maximum(0, right - left) * np.maximum(0, bottom - top)
        areas = np.maximum(0, boxes[:, 2] - boxes[:, 0]) * np.maximum(
            0, boxes[:, 3] - boxes[:, 1]
        )
        tracked_area = max(0, tracked_box[2] - tracked_box[0]) * max(
            0, tracked_box[3] - tracked_box[1]
        )
        union = areas + tracked_area - intersection
        ious = np.divide(
            intersection,
            union,
            out=np.zeros_like(intersection, dtype=np.float32),
            where=union > 0,
        )
        best = int(np.argmax(ious))
        if ious[best] >= 0.3:
            detection_index = candidates[best]
            assigned_ids[detection_index] = tracker_id
            available_indices.remove(detection_index)
    return assigned_ids


def append_detection_rows(
    writer,
    detections,
    tracker_ids,
    motion_states,
    roi_contour,
    timestamp,
    frame_number,
):
    if detections.class_id is None:
        return 0
    for index, (box, class_id) in enumerate(zip(detections.xyxy, detections.class_id)):
        x1, y1, x2, y2 = (float(coordinate) for coordinate in box)
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        in_roi = (
            roi_contour is None
            or cv2.pointPolygonTest(roi_contour, (center_x, y2), False) >= 0
        )
        tracker_id = int(tracker_ids[index])
        if not in_roi:
            state = "OUTSIDE_ROI"
            in_roi_value = False
        else:
            state = motion_states.get(tracker_id, "MOVING") if tracker_id >= 0 else "MOVING"
            in_roi_value = True
        confidence = (
            float(detections.confidence[index])
            if detections.confidence is not None
            else ""
        )
        writer.writerow(
            [
                timestamp,
                frame_number,
                tracker_id if tracker_id >= 0 else "",
                CLASS_NAMES.get(int(class_id), str(class_id)),
                confidence,
                x1,
                y1,
                x2,
                y2,
                center_x,
                center_y,
                in_roi_value,
                state,
            ]
        )
    return len(detections)


def annotate_boxes(frame, detections, parked_ids, hide_parked=False):
    height, width = frame.shape[:2]
    if detections.class_id is None:
        return frame

    tracker_ids = detections.tracker_id
    for index, (box, class_id) in enumerate(zip(detections.xyxy, detections.class_id)):
        x1, y1, x2, y2 = (int(round(value)) for value in box)
        x1 = max(0, min(x1, width - 1))
        y1 = max(0, min(y1, height - 1))
        x2 = max(0, min(x2, width - 1))
        y2 = max(0, min(y2, height - 1))
        tracker_id = tracker_ids[index] if tracker_ids is not None else None
        is_parked = tracker_id is not None and int(tracker_id) in parked_ids
        if is_parked and hide_parked:
            continue
        color = (120, 120, 120) if is_parked else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        tracker_label = int(tracker_id) if tracker_id is not None else -1
        label = (
            f"parked #{tracker_label}"
            if is_parked
            else f"{CLASS_NAMES.get(int(class_id), str(class_id))} #{tracker_label}"
        )
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.45
        text_size, baseline = cv2.getTextSize(label, font, font_scale, 1)
        label_top = max(0, y1 - text_size[1] - baseline - 6)
        label_right = min(width - 1, x1 + text_size[0] + 8)
        cv2.rectangle(frame, (x1, label_top), (label_right, y1), color, -1)
        text_y = max(text_size[1], y1 - baseline - 3)
        cv2.putText(
            frame,
            label,
            (x1 + 4, text_y),
            font,
            font_scale,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return frame


def draw_hud(
    frame,
    current,
    class_counts,
    unique_total,
    max_occupancy,
    moving_count,
    parked_count,
):
    lines = (
        "In area now: "
        f"{current}  (cars {class_counts[2]} moto {class_counts[3]} "
        f"bus {class_counts[5]} truck {class_counts[7]})",
        f"Unique since start: {unique_total}   Peak: {max_occupancy}",
        f"MOVING: {moving_count}   PARKED: {parked_count}",
    )
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.65
    thickness = 1
    metrics = [cv2.getTextSize(text, font, font_scale, thickness) for text in lines]
    band_width = min(frame.shape[1] - 1, max(size[0][0] for size in metrics) + 16)
    band_top = 48
    band_height = min(frame.shape[0] - 1, 130)
    overlay = frame.copy()
    cv2.rectangle(
        overlay,
        (0, band_top),
        (band_width, band_height),
        (0, 0, 0),
        -1,
    )
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

    for text, y in zip(lines, (70, 95, 120)):
        cv2.putText(
            frame,
            text,
            (10, y),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )
    return frame


def congestion_level(current, threshold):
    if current < 0.6 * threshold:
        return "GREEN"
    if current < threshold:
        return "YELLOW"
    return "RED"


def update_alert_episode(current, threshold, now, alert_active, below_since):
    below_rearm_level = current < 0.6 * threshold
    if below_rearm_level:
        if below_since is None:
            below_since = now
        elif now - below_since >= 5.0:
            alert_active = False
    else:
        below_since = None

    should_alert = current >= threshold and not alert_active
    if should_alert:
        alert_active = True
        below_since = None
    return alert_active, below_since, should_alert


def draw_congestion_banner(frame, current, level, frame_number):
    if level == "RED" and (frame_number // 15) % 2 == 1:
        return frame

    colors = {
        "GREEN": (0, 150, 0),
        "YELLOW": (0, 190, 255),
        "RED": (0, 0, 220),
    }
    suffix = "RED ALERT" if level == "RED" else level
    text = f"CONGESTION: {current} vehicles - {suffix}"
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.75
    thickness = 2
    (text_width, text_height), baseline = cv2.getTextSize(text, font, scale, thickness)
    x1 = max(0, (frame.shape[1] - text_width - 28) // 2)
    x2 = min(frame.shape[1] - 1, x1 + text_width + 28)
    y1 = 8
    y2 = min(frame.shape[0] - 1, y1 + text_height + baseline + 18)
    cv2.rectangle(frame, (x1, y1), (x2, y2), colors[level], -1, cv2.LINE_AA)
    text_x = max(0, (frame.shape[1] - text_width) // 2)
    cv2.putText(
        frame,
        text,
        (text_x, min(frame.shape[0] - 1, y1 + text_height + 6)),
        font,
        scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )
    return frame


def write_occupancy_snapshot(
    csv_writer,
    csv_file,
    camera,
    current,
    unique_total,
    max_occupancy,
    class_counts,
    parked_count,
    level,
):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    csv_writer.writerow(
        [
            timestamp,
            camera,
            current,
            unique_total,
            max_occupancy,
            class_counts[2],
            class_counts[3],
            class_counts[5],
            class_counts[7],
            parked_count,
            level,
        ]
    )
    csv_file.flush()


def ensure_occupancy_csv_schema(csv_path):
    expected_header = [
        "timestamp",
        "camera",
        "current",
        "unique_total",
        "max_so_far",
        "cars",
        "motorcycles",
        "buses",
        "trucks",
        "parked",
        "level",
    ]
    old_header = [column for column in expected_header if column != "parked"]
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return expected_header

    with csv_path.open("r", newline="", encoding="utf-8") as existing_file:
        rows = list(csv.reader(existing_file))
    if not rows or rows[0] == expected_header:
        return expected_header
    if rows[0] != old_header:
        raise ValueError(f"Unexpected occupancy CSV header in {csv_path}")

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            newline="",
            encoding="utf-8",
            dir=csv_path.parent,
            prefix=f"{csv_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            writer = csv.writer(temporary_file)
            writer.writerow(expected_header)
            for row in rows[1:]:
                if len(row) == len(old_header):
                    row.insert(-1, "0")
                writer.writerow(row)
        os.replace(temporary_path, csv_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return expected_header


def process(args):
    capture = None
    csv_file = None
    detections_file = None
    processed_frames = 0

    try:
        capture = cv2.VideoCapture(args.source)
        if args.is_stream:
            success, frame = capture.read() if capture.isOpened() else (False, None)
            if not success or frame is None:
                capture, frame = reconnect_stream(args.source, capture)
        else:
            if not capture.isOpened():
                raise RuntimeError(f"Unable to open video file: {args.source}")
            success, frame = capture.read()
            if not success or frame is None:
                raise RuntimeError(f"Unable to read a frame from video file: {args.source}")

        frame_height, frame_width = frame.shape[:2]
        crop_top, crop_bottom, crop_left, crop_right = validate_crop(
            args.crop, frame_height, frame_width
        )
        roi_contour = validate_roi(args.roi, frame_height, frame_width)
        output_dir = Path("results") / args.camera
        os.makedirs(output_dir, exist_ok=True)
        roi_points = (
            tuple(map(tuple, roi_contour.reshape((4, 2)).tolist()))
            if roi_contour is not None
            else None
        )
        print(
            f"Occupancy mode. Alert threshold: {args.alert_at} vehicles. "
            f"ROI points: {roi_points}",
            flush=True,
        )
        print(
            f"Park filter: stationary for {args.park_seconds}s with "
            "center range <=12px = PARKED",
            flush=True,
        )

        reported_fps = capture.get(cv2.CAP_PROP_FPS)
        fps = reported_fps if math.isfinite(reported_fps) and reported_fps > 0 else 30.0
        if fps != reported_fps:
            print("Source FPS unavailable; using 30 FPS for output timing.", file=sys.stderr)

        tracker = sv.ByteTrack(
            track_activation_threshold=0.10,
            lost_track_buffer=60,
            minimum_matching_threshold=0.5,
            minimum_consecutive_frames=1,
        )
        if hasattr(tracker, "det_thresh"):
            tracker.det_thresh = 0.10
        model = YOLO(str(MODEL_PATH))

        unique_seen = set()
        motion_histories = {}
        motion_last_seen = {}
        motion_states = {}
        parked_spots = []
        spot_parked_ids = {}
        max_occupancy = 0
        max_occupancy_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert_active = False
        below_alert_since = None
        current = 0
        class_counts = {class_id: 0 for class_id in VEHICLE_CLASSES}

        csv_path = output_dir / "occupancy.csv"
        write_header = not csv_path.exists() or csv_path.stat().st_size == 0
        occupancy_header = ensure_occupancy_csv_schema(csv_path)
        csv_file = csv_path.open("a", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        if write_header:
            csv_writer.writerow(occupancy_header)
            csv_file.flush()

        alerts_path = output_dir / "alerts.csv"
        detections_path = output_dir / "detections.csv"
        detections_header = [
            "timestamp_iso",
            "frame_idx",
            "tracker_id",
            "class_name",
            "confidence",
            "x1",
            "y1",
            "x2",
            "y2",
            "center_x",
            "center_y",
            "in_roi",
            "state",
        ]
        detections_write_header = (
            not detections_path.exists() or detections_path.stat().st_size == 0
        )
        detections_file = detections_path.open("a", newline="", encoding="utf-8")
        detections_writer = csv.writer(detections_file)
        if detections_write_header:
            detections_writer.writerow(detections_header)
            detections_file.flush()
        detection_rows_since_flush = 0

        next_csv_flush_seconds = CSV_FLUSH_SECONDS
        last_csv_flush_seconds = 0

        while True:
            cropped_frame = frame[crop_top:crop_bottom, crop_left:crop_right]
            prediction = model.predict(
                source=cropped_frame,
                conf=0.15,
                imgsz=args.imgsz,
                classes=[2, 3, 5, 7],
                verbose=False,
            )[0]
            detections = sv.Detections.from_ultralytics(prediction)
            detections = restore_detection_coordinates(
                detections, crop_left, crop_top
            )

            tracked_detections = tracker.update_with_detections(detections)
            frame_motion_states = update_motion_classification(
                tracked_detections,
                processed_frames + 1,
                motion_histories,
                motion_last_seen,
                motion_states,
                parked_spots,
                spot_parked_ids,
                fps,
                args.park_seconds,
            )
            raw_tracker_ids = associate_tracker_ids(detections, tracked_detections)
            in_roi_tracked = tracked_detections_in_roi(
                tracked_detections, roi_contour
            )
            processed_frames += 1

            now = datetime.now()
            timestamp = now.isoformat(sep=" ", timespec="seconds")
            detection_rows_since_flush += append_detection_rows(
                detections_writer,
                detections,
                raw_tracker_ids,
                frame_motion_states,
                roi_contour,
                timestamp,
                processed_frames,
            )
            if detection_rows_since_flush >= 1000:
                detections_file.flush()
                detection_rows_since_flush = 0

            roi_tracker_ids = in_roi_tracked.tracker_id
            parked_mask = np.asarray(
                [
                    frame_motion_states.get(int(tracker_id), "MOVING") == "PARKED"
                    for tracker_id in roi_tracker_ids
                ],
                dtype=bool,
            )
            moving_detections = in_roi_tracked[~parked_mask]
            parked_detections = in_roi_tracked[parked_mask]
            if moving_detections.tracker_id is not None:
                unique_seen.update(
                    int(tracker_id)
                    for tracker_id in moving_detections.tracker_id
                    if tracker_id is not None and int(tracker_id) >= 0
                )
            current = len(moving_detections)
            parked_count = len(parked_detections)
            class_counts = {
                class_id: int(np.count_nonzero(moving_detections.class_id == class_id))
                if moving_detections.class_id is not None
                else 0
                for class_id in VEHICLE_CLASSES
            }
            if current > max_occupancy:
                max_occupancy = current
                max_occupancy_timestamp = timestamp
                print(
                    f"New occupancy peak: {max_occupancy} at "
                    f"{max_occupancy_timestamp}",
                    flush=True,
                )

            level = congestion_level(current, args.alert_at)
            alert_active, below_alert_since, should_alert = update_alert_episode(
                current,
                args.alert_at,
                time.monotonic(),
                alert_active,
                below_alert_since,
            )
            if should_alert:
                print(
                    f"ALERT at {timestamp}: {current} vehicles "
                    f"(threshold {args.alert_at})",
                    flush=True,
                )
                write_alert_header = (
                    not alerts_path.exists() or alerts_path.stat().st_size == 0
                )
                with alerts_path.open("a", newline="", encoding="utf-8") as alert_file:
                    alert_writer = csv.writer(alert_file)
                    if write_alert_header:
                        alert_writer.writerow(
                            ["timestamp", "camera", "vehicles", "threshold"]
                        )
                    alert_writer.writerow(
                        [timestamp, args.camera, current, args.alert_at]
                    )
                    alert_file.flush()
                try:
                    winsound = importlib.import_module("winsound")
                    winsound.Beep(880, 300)
                except Exception:
                    pass

            parked_ids = (
                set(map(int, parked_detections.tracker_id.tolist()))
                if parked_detections.tracker_id is not None
                else set()
            )
            annotated = annotate_boxes(
                frame.copy(),
                in_roi_tracked,
                parked_ids,
                hide_parked=args.hide_parked,
            )
            if roi_contour is not None:
                cv2.polylines(
                    annotated,
                    [roi_contour],
                    isClosed=True,
                    color=(255, 255, 0),
                    thickness=2,
                )
            annotated = draw_hud(
                annotated,
                current,
                class_counts,
                len(unique_seen),
                max_occupancy,
                current,
                0 if args.hide_parked else parked_count,
            )
            annotated = draw_congestion_banner(
                annotated, current, level, processed_frames
            )

            cv2.imshow(f"Vehicle detection - {args.camera}", annotated)

            elapsed_video_seconds = processed_frames / fps
            while elapsed_video_seconds >= next_csv_flush_seconds:
                write_occupancy_snapshot(
                    csv_writer,
                    csv_file,
                    args.camera,
                    current,
                    len(unique_seen),
                    max_occupancy,
                    class_counts,
                    parked_count,
                    level,
                )
                last_csv_flush_seconds = next_csv_flush_seconds
                next_csv_flush_seconds += CSV_FLUSH_SECONDS

            if processed_frames % 100 == 0:
                print(
                    f"Frame {processed_frames}: current={current} "
                    f"unique={len(unique_seen)} peak={max_occupancy} "
                    f"level={level}",
                    flush=True,
                )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            success, next_frame = capture.read()
            if success and next_frame is not None:
                frame = next_frame
            elif args.is_stream:
                capture, frame = reconnect_stream(args.source, capture)
            else:
                break

        level = congestion_level(current, args.alert_at)
        elapsed_video_seconds = processed_frames / fps
        if elapsed_video_seconds > last_csv_flush_seconds:
            write_occupancy_snapshot(
                csv_writer,
                csv_file,
                args.camera,
                current,
                len(unique_seen),
                max_occupancy,
                class_counts,
                parked_count,
                level,
            )

        print(
            f"Final occupancy for {args.camera}: current={current}, "
            f"unique={len(unique_seen)}, peak={max_occupancy} "
            f"at {max_occupancy_timestamp}, level={level}"
        )
        for class_id in VEHICLE_CLASSES:
            print(f"  {CLASS_NAMES[class_id]} currently in ROI: {class_counts[class_id]}")
        print(f"Processed {processed_frames} frames.")
        return 0
    finally:
        if capture is not None:
            capture.release()
        if csv_file is not None:
            csv_file.close()
        if detections_file is not None:
            detections_file.flush()
            detections_file.close()
        cv2.destroyAllWindows()


def main():
    args = parse_args()
    try:
        global cv2, sv, YOLO, np
        cv2 = importlib.import_module("cv2")
        sv = importlib.import_module("supervision")
        YOLO = importlib.import_module("ultralytics").YOLO
        np = importlib.import_module("numpy")
        return process(args)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

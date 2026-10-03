import argparse
import csv
from datetime import datetime
import importlib
import math
from pathlib import Path
import re
import sys
import time
from typing import Any
from urllib.parse import urlparse

cv2: Any = None
sv: Any = None
YOLO: Any = None
VEHICLE_CLASSES = (2, 3, 5, 7)
CLASS_NAMES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}
CSV_FLUSH_SECONDS = 60
VIDEO_SEGMENT_SECONDS = 30 * 60
STREAM_RETRIES = 5
STREAM_RETRY_WAIT_SECONDS = 10


def parse_args():
    parser = argparse.ArgumentParser(
        description="Count vehicles crossing a line in a video or HLS stream."
    )
    parser.add_argument("source", help="Local .mp4 path or HLS .m3u8 URL")
    parser.add_argument("camera", help="Camera name used in output filenames and CSV")
    parser.add_argument(
        "--line-position",
        type=float,
        default=0.6,
        metavar="FRACTION",
        help="Horizontal counting line height as a fraction of frame height (default: 0.6)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="YOLO inference image size (default: 640)",
    )
    args = parser.parse_args()

    parsed_source = urlparse(args.source)
    is_stream = parsed_source.scheme.lower() in ("http", "https") and parsed_source.path.lower().endswith(
        ".m3u8"
    )
    if not is_stream and Path(args.source).suffix.lower() != ".mp4":
        parser.error("source must be a local .mp4 path or an HTTP(S) .m3u8 URL")
    if not is_stream and not Path(args.source).is_file():
        parser.error(f"video file does not exist: {args.source}")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.camera):
        parser.error("camera must contain only letters, numbers, underscores, or hyphens")
    if not 0.0 <= args.line_position <= 1.0:
        parser.error("--line-position must be between 0 and 1")
    if args.imgsz <= 0:
        parser.error("--imgsz must be greater than zero")
    args.is_stream = is_stream
    return args


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


def make_line_zones(frame_width, frame_height, line_position):
    line_y = round((frame_height - 1) * line_position)
    start = sv.Point(x=0, y=line_y)
    end = sv.Point(x=frame_width - 1, y=line_y)
    zones = {
        class_id: sv.LineZone(start=start, end=end)
        for class_id in VEHICLE_CLASSES
    }
    return line_y, zones


def filter_class(detections, class_id):
    if detections.class_id is None:
        return detections[:0]
    return detections[detections.class_id == class_id]


def count_snapshot(line_zones):
    return {
        class_id: {
            "in": int(line_zones[class_id].in_count),
            "out": int(line_zones[class_id].out_count),
        }
        for class_id in VEHICLE_CLASSES
    }


def open_video_writer(camera, frame_width, frame_height, fps, segment_number):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    suffix = f"_{segment_number:03d}" if segment_number else ""
    output_path = f"output_{camera}_{timestamp}{suffix}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))
    if not writer.isOpened():
        writer.release()
        raise RuntimeError(f"Unable to create output video: {output_path}")
    print(f"Writing annotated video: {output_path}", flush=True)
    return writer


def process(args):
    capture = cv2.VideoCapture(args.source)
    writer = None
    csv_file = None
    window_name = f"Traffic counter - {args.camera}"
    processed_frames = 0
    segment_start_frame = 0
    segment_number = 0

    try:
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
        reported_fps = capture.get(cv2.CAP_PROP_FPS)
        fps = reported_fps if math.isfinite(reported_fps) and reported_fps > 0 else 30.0
        if fps != reported_fps:
            print("Source FPS unavailable; using 30 FPS for output timing.", file=sys.stderr)

        line_y, line_zones = make_line_zones(frame_width, frame_height, args.line_position)
        box_annotator = sv.BoxAnnotator()
        label_annotator = sv.LabelAnnotator()
        tracker = sv.ByteTrack()
        model = YOLO("yolo11m.pt")

        csv_path = Path(f"counts_{args.camera}.csv")
        write_header = not csv_path.exists() or csv_path.stat().st_size == 0
        csv_file = csv_path.open("a", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        if write_header:
            csv_writer.writerow(
                ["timestamp", "camera", "direction", "vehicle_class", "count"]
            )
            csv_file.flush()

        writer = open_video_writer(args.camera, frame_width, frame_height, fps, segment_number)
        next_csv_flush_seconds = CSV_FLUSH_SECONDS
        last_csv_flush_seconds = 0

        while True:
            result = model.predict(
                source=frame,
                classes=list(VEHICLE_CLASSES),
                imgsz=args.imgsz,
                verbose=False,
            )[0]
            detections = sv.Detections.from_ultralytics(result)
            detections = tracker.update_with_detections(detections)

            for class_id in VEHICLE_CLASSES:
                line_zones[class_id].trigger(filter_class(detections, class_id))

            labels = []
            for index in range(len(detections)):
                class_id = detections.class_id[index] if detections.class_id is not None else None
                tracker_id = (
                    detections.tracker_id[index]
                    if detections.tracker_id is not None
                    else None
                )
                class_name = CLASS_NAMES.get(int(class_id), str(class_id)) if class_id is not None else "vehicle"
                track_label = f"#{int(tracker_id)}" if tracker_id is not None else ""
                labels.append(f"{class_name} {track_label}".strip())

            annotated = frame.copy()
            annotated = box_annotator.annotate(scene=annotated, detections=detections)
            annotated = label_annotator.annotate(
                scene=annotated, detections=detections, labels=labels
            )
            cv2.line(annotated, (0, line_y), (frame_width - 1, line_y), (0, 255, 255), 2)

            counts = count_snapshot(line_zones)
            total_in = sum(class_counts["in"] for class_counts in counts.values())
            total_out = sum(class_counts["out"] for class_counts in counts.values())
            cv2.putText(
                annotated,
                f"IN: {total_in}  OUT: {total_out}",
                (12, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            elapsed_video_seconds = processed_frames / fps
            if elapsed_video_seconds - (segment_start_frame / fps) >= VIDEO_SEGMENT_SECONDS:
                writer.release()
                segment_number += 1
                writer = open_video_writer(
                    args.camera, frame_width, frame_height, fps, segment_number
                )
                segment_start_frame = processed_frames

            writer.write(annotated)
            cv2.imshow(window_name, annotated)
            processed_frames += 1

            elapsed_video_seconds = processed_frames / fps
            while elapsed_video_seconds >= next_csv_flush_seconds:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                counts = count_snapshot(line_zones)
                for class_id in VEHICLE_CLASSES:
                    for direction in ("in", "out"):
                        csv_writer.writerow(
                            [
                                timestamp,
                                args.camera,
                                direction,
                                CLASS_NAMES[class_id],
                                counts[class_id][direction],
                            ]
                        )
                csv_file.flush()
                last_csv_flush_seconds = next_csv_flush_seconds
                next_csv_flush_seconds += CSV_FLUSH_SECONDS

            if processed_frames % 100 == 0:
                print(
                    f"Frame {processed_frames}: IN={total_in} OUT={total_out}",
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

        final_counts = count_snapshot(line_zones)
        elapsed_video_seconds = processed_frames / fps
        if elapsed_video_seconds > last_csv_flush_seconds:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for class_id in VEHICLE_CLASSES:
                for direction in ("in", "out"):
                    csv_writer.writerow(
                        [
                            timestamp,
                            args.camera,
                            direction,
                            CLASS_NAMES[class_id],
                            final_counts[class_id][direction],
                        ]
                    )
            csv_file.flush()

        print(f"Final counts for {args.camera}:")
        for class_id in VEHICLE_CLASSES:
            print(
                f"  {CLASS_NAMES[class_id]}: IN={final_counts[class_id]['in']} "
                f"OUT={final_counts[class_id]['out']}"
            )
        print(f"Processed {processed_frames} frames.")
        return 0
    finally:
        if writer is not None:
            writer.release()
        if capture is not None:
            capture.release()
        if csv_file is not None:
            csv_file.close()
        cv2.destroyAllWindows()


def main():
    args = parse_args()
    try:
        global cv2, sv, YOLO
        cv2 = importlib.import_module("cv2")
        sv = importlib.import_module("supervision")
        YOLO = importlib.import_module("ultralytics").YOLO
        return process(args)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
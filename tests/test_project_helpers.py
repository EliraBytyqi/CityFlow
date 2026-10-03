import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import detect_cars
import traffic_counter


class ModelPathTests(unittest.TestCase):
    def test_both_scripts_resolve_the_bundled_model(self):
        expected = Path(__file__).resolve().parents[1] / "yolo11m.pt"

        self.assertEqual(detect_cars.MODEL_PATH, expected)
        self.assertEqual(traffic_counter.MODEL_PATH.parent, expected.parent)
        self.assertEqual(traffic_counter.MODEL_PATH.name, "yolo11n.pt")
        self.assertTrue(expected.is_file())


class PureHelperTests(unittest.TestCase):
    def test_current_roi_occupancy_uses_only_this_frames_inside_tracks(self):
        polygon = traffic_counter.parse_polygon("0,0,100,0,100,100,0,100")
        first_frame = [
            (4, "car", 0.91, (10, 10, 30, 30)),
            (7, "truck", 0.88, (50, 50, 70, 70)),
            (9, "motorcycle", 0.95, (150, 150, 170, 170)),
        ]
        evaluated, current_tracks, counts = traffic_counter.evaluate_tracks(
            first_frame, polygon
        )
        self.assertEqual(set(current_tracks), {4, 7})
        self.assertEqual(counts["car"], 1)
        self.assertEqual(counts["truck"], 1)
        self.assertEqual(counts["motorcycle"], 0)
        self.assertFalse(evaluated[2]["inside_roi"])

        next_frame = [
            (4, "car", 0.90, (120, 10, 140, 30)),
            (12, "bus", 0.86, (20, 20, 40, 40)),
        ]
        _, current_tracks, counts = traffic_counter.evaluate_tracks(next_frame, polygon)
        self.assertEqual(set(current_tracks), {12})
        self.assertEqual(counts["car"], 0)
        self.assertEqual(counts["truck"], 0)
        self.assertEqual(counts["bus"], 1)
        self.assertEqual(len(current_tracks), counts["bus"])

        with self.assertRaises(traffic_counter.argparse.ArgumentTypeError):
            traffic_counter.parse_polygon("0,0,10,10")

    def test_occupancy_alert_transitions_and_cooldown(self):
        active, event, last_alert = traffic_counter.update_alert_state(
            15, 15, False, -float("inf"), 10.0, 30.0
        )
        self.assertEqual((active, event, last_alert), (True, "ALERT_STARTED", 10.0))
        active, event, last_alert = traffic_counter.update_alert_state(
            18, 15, active, last_alert, 20.0, 30.0
        )
        self.assertEqual((active, event, last_alert), (True, None, 10.0))
        active, event, last_alert = traffic_counter.update_alert_state(
            18, 15, active, last_alert, 40.0, 30.0
        )
        self.assertEqual((active, event, last_alert), (True, "ALERT_REMINDER", 40.0))
        active, event, last_alert = traffic_counter.update_alert_state(
            14, 15, active, last_alert, 41.0, 30.0
        )
        self.assertEqual((active, event, last_alert), (False, "ALERT_CLEARED", 40.0))

    def test_crop_and_roi_parsers(self):
        self.assertEqual(detect_cars.parse_crop("2,10,3,20"), (2, 10, 3, 20))
        self.assertEqual(
            detect_cars.parse_roi("0,1,2,3,4,5,6,7"),
            (0, 1, 2, 3, 4, 5, 6, 7),
        )
        with self.assertRaises(detect_cars.argparse.ArgumentTypeError):
            detect_cars.parse_crop("0,0,0,10")
        with self.assertRaises(detect_cars.argparse.ArgumentTypeError):
            detect_cars.parse_roi("0,1,2,3")

    def test_congestion_levels_and_alert_rearming(self):
        self.assertEqual(detect_cars.congestion_level(4, 8), "GREEN")
        self.assertEqual(detect_cars.congestion_level(6, 8), "YELLOW")
        self.assertEqual(detect_cars.congestion_level(8, 8), "RED")

        active, below_since, should_alert = detect_cars.update_alert_episode(
            8, 8, 0.0, False, None
        )
        self.assertEqual((active, below_since, should_alert), (True, None, True))
        active, below_since, should_alert = detect_cars.update_alert_episode(
            4, 8, 1.0, active, below_since
        )
        self.assertEqual((active, below_since, should_alert), (True, 1.0, False))
        active, below_since, should_alert = detect_cars.update_alert_episode(
            4, 8, 6.0, active, below_since
        )
        self.assertEqual((active, below_since, should_alert), (False, 1.0, False))


class ArgumentValidationTests(unittest.TestCase):
    def parse_args(self, module, arguments):
        with patch.object(sys, "argv", ["script.py", *arguments]):
            with contextlib.redirect_stderr(io.StringIO()):
                return module.parse_args()

    def test_traffic_counter_accepts_existing_mp4_and_hls(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            video_path = Path(temporary_directory) / "sample.mp4"
            video_path.touch()
            local_args = self.parse_args(
                traffic_counter, [str(video_path), "north_gate"]
            )
            self.assertFalse(local_args.is_stream)

        stream_args = self.parse_args(
            traffic_counter,
            [
                "https://example.invalid/playlist.m3u8",
                "north_gate",
                "--threshold",
                "12",
                "--conf",
                "0.5",
            ],
        )
        self.assertTrue(stream_args.is_stream)
        self.assertEqual(stream_args.camera_name, "north_gate")
        self.assertEqual(stream_args.threshold, 12)
        self.assertEqual(stream_args.conf, 0.5)
        self.assertEqual(stream_args.roi, tuple(traffic_counter.ROI_POLYGON))

    def test_detect_cars_accepts_hls_and_rejects_invalid_camera(self):
        args = self.parse_args(
            detect_cars,
            ["https://example.invalid/playlist.m3u8", "north_gate"],
        )
        self.assertTrue(args.is_stream)
        with self.assertRaises(SystemExit):
            self.parse_args(
                detect_cars,
                ["https://example.invalid/playlist.m3u8", "north gate"],
            )


if __name__ == "__main__":
    unittest.main()
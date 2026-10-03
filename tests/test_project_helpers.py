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
    def test_line_crossings_and_polygon_membership(self):
        self.assertEqual(traffic_counter.crossing_direction(4, 6, 5), "down")
        self.assertEqual(traffic_counter.crossing_direction(6, 4, 5), "up")
        self.assertIsNone(traffic_counter.crossing_direction(4, 4.5, 5))

        polygon = traffic_counter.parse_polygon("0,0,10,0,10,10,0,10")
        self.assertTrue(traffic_counter.inside_polygon((5, 5), polygon))
        self.assertTrue(traffic_counter.inside_polygon((0, 5), polygon))
        self.assertFalse(traffic_counter.inside_polygon((15, 5), polygon))
        with self.assertRaises(traffic_counter.argparse.ArgumentTypeError):
            traffic_counter.parse_polygon("0,0,10,10")

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
            ["https://example.invalid/playlist.m3u8", "north_gate"],
        )
        self.assertTrue(stream_args.is_stream)

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
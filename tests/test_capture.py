"""Unit tests for capture module."""

import sys
import os
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.capture import ScreenCapture


class TestScreenCapture:
    def test_roi_validation_fails_on_zero(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
monitor:
  index: 0
roi:
  elevator_1: [0, 0, 0, 0]
  panel_1: [0, 0, 0, 0]
  elevator_2: [0, 0, 0, 0]
  panel_2: [0, 0, 0, 0]
capture:
  save_debug_frames: false
""")
        with pytest.raises(ValueError, match="ROI .* is not set"):
            ScreenCapture(str(config_file))

    def test_crop_roi_correct_size(self):
        """Test that crop_roi returns correct dimensions."""
        capture = ScreenCapture.__new__(ScreenCapture)
        capture.roi = {
            "elevator_1": [10, 20, 100, 80],
            "panel_1": [200, 30, 50, 60],
            "elevator_2": [10, 200, 100, 80],
            "panel_2": [200, 200, 50, 60],
        }
        capture.save_debug = False

        # Create a test image
        full_image = np.zeros((500, 500, 3), dtype=np.uint8)
        full_image[20:100, 10:110] = 128  # Mark elevator_1 area

        cropped = capture.crop_roi(full_image, "elevator_1")
        assert cropped.shape[0] == 80  # height
        assert cropped.shape[1] == 100  # width

    def test_crop_roi_clamped_to_bounds(self):
        """Test that ROI is clamped when exceeding image bounds."""
        capture = ScreenCapture.__new__(ScreenCapture)
        capture.roi = {
            "elevator_1": [450, 450, 200, 200],  # exceeds 500x500 image
        }

        full_image = np.zeros((500, 500, 3), dtype=np.uint8)
        cropped = capture.crop_roi(full_image, "elevator_1")
        # Should be clamped
        assert cropped.shape[0] <= 500
        assert cropped.shape[1] <= 500

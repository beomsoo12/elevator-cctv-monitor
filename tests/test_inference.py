"""Unit tests for inference engine."""

import sys
import os
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.inference import ConfirmationBuffer, InferenceEngine


class TestConfirmationBuffer:
    def test_empty_buffer_not_confirmed(self):
        buf = ConfirmationBuffer(3)
        assert buf.is_confirmed() is False
        assert buf.get_value() is None

    def test_partial_buffer_not_confirmed(self):
        buf = ConfirmationBuffer(3)
        buf.push(True)
        buf.push(True)
        assert buf.is_confirmed() is False

    def test_all_same_confirmed(self):
        buf = ConfirmationBuffer(3)
        buf.push(True)
        buf.push(True)
        buf.push(True)
        assert buf.is_confirmed() is True
        assert buf.get_value() is True

    def test_mixed_not_confirmed(self):
        buf = ConfirmationBuffer(3)
        buf.push(True)
        buf.push(False)
        buf.push(True)
        assert buf.is_confirmed() is False

    def test_reset(self):
        buf = ConfirmationBuffer(3)
        buf.push(True)
        buf.push(True)
        buf.push(True)
        assert buf.is_confirmed() is True
        buf.reset()
        assert buf.is_confirmed() is False

    def test_rolling_window(self):
        buf = ConfirmationBuffer(3)
        buf.push(1)
        buf.push(2)
        buf.push(3)
        assert buf.is_confirmed() is False
        buf.push(3)
        buf.push(3)
        assert buf.is_confirmed() is True
        assert buf.get_value() == 3

    def test_size_one(self):
        buf = ConfirmationBuffer(1)
        buf.push("x")
        assert buf.is_confirmed() is True
        assert buf.get_value() == "x"


class TestInferenceEngine:
    @patch("src.inference.tf.keras.models.load_model")
    @patch("src.inference.os.path.exists", return_value=True)
    @patch("builtins.open", MagicMock())
    @patch("src.inference.yaml.safe_load")
    def test_predict_cargo(self, mock_yaml, mock_exists, mock_load):
        mock_yaml.return_value = {
            "model": {
                "cargo_threshold": 0.75,
                "floor_threshold": 0.85,
                "confirm_frames": 5,
                "input_size": [224, 224],
            }
        }
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([[0.9]])
        mock_load.return_value = mock_model

        engine = InferenceEngine.__new__(InferenceEngine)
        engine.cargo_threshold = 0.75
        engine.floor_threshold = 0.85
        engine.input_size = (224, 224)
        engine.cargo_model = mock_model
        engine.floor_model = mock_model
        engine.cargo_buffers = {
            "elevator_1": ConfirmationBuffer(5),
            "elevator_2": ConfirmationBuffer(5),
        }
        engine.floor_buffers = {
            "elevator_1": ConfirmationBuffer(3),
            "elevator_2": ConfirmationBuffer(3),
        }

        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.predict_cargo(dummy_img)

        assert result["is_loaded"] is True
        assert result["raw_score"] == pytest.approx(0.9)
        assert result["confidence"] == pytest.approx(0.9)

    @patch("src.inference.tf.keras.models.load_model")
    @patch("src.inference.os.path.exists", return_value=True)
    @patch("builtins.open", MagicMock())
    @patch("src.inference.yaml.safe_load")
    def test_predict_floor(self, mock_yaml, mock_exists, mock_load):
        mock_yaml.return_value = {
            "model": {
                "cargo_threshold": 0.75,
                "floor_threshold": 0.85,
                "confirm_frames": 5,
                "input_size": [224, 224],
            }
        }
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([[0.05, 0.05, 0.85, 0.05]])
        mock_load.return_value = mock_model

        engine = InferenceEngine.__new__(InferenceEngine)
        engine.cargo_threshold = 0.75
        engine.floor_threshold = 0.85
        engine.input_size = (224, 224)
        engine.cargo_model = mock_model
        engine.floor_model = mock_model
        engine.cargo_buffers = {
            "elevator_1": ConfirmationBuffer(5),
            "elevator_2": ConfirmationBuffer(5),
        }
        engine.floor_buffers = {
            "elevator_1": ConfirmationBuffer(3),
            "elevator_2": ConfirmationBuffer(3),
        }

        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.predict_floor(dummy_img)

        assert result["floor"] == 3
        assert result["confidence"] == pytest.approx(0.85)

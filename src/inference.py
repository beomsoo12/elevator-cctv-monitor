"""ML inference engine - cargo detection and floor recognition."""

import os
from collections import deque
from datetime import datetime
import numpy as np
import cv2

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
import tensorflow as tf
import yaml


class ConfirmationBuffer:
    """Requires N consecutive identical results to confirm a prediction."""

    def __init__(self, size):
        self.size = size
        self.buffer = deque(maxlen=size)

    def push(self, value):
        self.buffer.append(value)

    def is_confirmed(self):
        if len(self.buffer) < self.size:
            return False
        return len(set(self.buffer)) == 1

    def get_value(self):
        if self.is_confirmed():
            return self.buffer[-1]
        return None

    def reset(self):
        self.buffer.clear()


class InferenceEngine:
    """Manages cargo and floor models for prediction."""

    def __init__(self, config_path="config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        model_config = config["model"]
        self.cargo_threshold = model_config["cargo_threshold"]
        self.floor_threshold = model_config["floor_threshold"]
        self.input_size = tuple(model_config["input_size"])
        confirm_frames = model_config["confirm_frames"]

        cargo_path = "models/cargo_model.keras"
        floor_path = "models/floor_model.keras"

        if not os.path.exists(cargo_path):
            raise FileNotFoundError(
                f"Cargo model not found: {cargo_path}\n"
                "Run 'python src/train_cargo.py' first."
            )
        if not os.path.exists(floor_path):
            raise FileNotFoundError(
                f"Floor model not found: {floor_path}\n"
                "Run 'python src/train_floor.py' first."
            )

        self.cargo_model = tf.keras.models.load_model(cargo_path)
        self.floor_model = tf.keras.models.load_model(floor_path)

        # Confirmation buffers (per elevator)
        self.cargo_buffers = {
            "elevator_1": ConfirmationBuffer(confirm_frames),
            "elevator_2": ConfirmationBuffer(confirm_frames),
        }
        self.floor_buffers = {
            "elevator_1": ConfirmationBuffer(3),
            "elevator_2": ConfirmationBuffer(3),
        }

    def _preprocess(self, image):
        """Preprocess image for model input: BGR->RGB, resize, normalize."""
        img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, self.input_size)
        img = img.astype(np.float32) / 255.0
        return np.expand_dims(img, axis=0)

    def predict_cargo(self, image):
        """Predict cargo presence."""
        preprocessed = self._preprocess(image)
        raw_score = float(self.cargo_model.predict(preprocessed, verbose=0)[0][0])
        return {
            "is_loaded": raw_score > self.cargo_threshold,
            "confidence": raw_score if raw_score > 0.5 else 1.0 - raw_score,
            "raw_score": raw_score,
        }

    def predict_floor(self, image):
        """Predict floor number."""
        preprocessed = self._preprocess(image)
        probabilities = self.floor_model.predict(preprocessed, verbose=0)[0]
        floor = int(np.argmax(probabilities)) + 1
        confidence = float(probabilities[floor - 1])
        return {
            "floor": floor if confidence >= self.floor_threshold else 0,
            "confidence": confidence,
            "probabilities": [float(p) for p in probabilities],
        }

    def predict_all(self, elevator_img, panel_img):
        """Run both predictions and return combined result."""
        cargo_result = self.predict_cargo(elevator_img)
        floor_result = self.predict_floor(panel_img)
        return {
            "cargo": cargo_result,
            "floor": floor_result,
            "timestamp": datetime.now(),
        }

    def predict_with_confirmation(self, elevator_id, elevator_img, panel_img):
        """Predict with confirmation buffer for stable results."""
        result = self.predict_all(elevator_img, panel_img)

        # Update cargo buffer
        cargo_buf = self.cargo_buffers[elevator_id]
        cargo_buf.push(result["cargo"]["is_loaded"])
        cargo_confirmed = cargo_buf.get_value()

        # Update floor buffer
        floor_buf = self.floor_buffers[elevator_id]
        floor_buf.push(result["floor"]["floor"])
        floor_confirmed = floor_buf.get_value()

        return {
            "raw": result,
            "cargo_confirmed": cargo_confirmed,
            "floor_confirmed": floor_confirmed,
        }

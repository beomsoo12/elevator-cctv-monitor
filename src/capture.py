"""Screen capture and ROI cropping module."""

import os
import time
import numpy as np
import cv2
import yaml
import mss


class ScreenCapture:
    """Captures screen and crops ROI regions."""

    def __init__(self, config_path="config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.monitor_index = self.config["monitor"]["index"]
        self.roi = self.config["roi"]
        self.save_debug = self.config["capture"].get("save_debug_frames", False)
        self.sct = mss.mss()

        # Validate ROI
        for name, coords in self.roi.items():
            if coords == [0, 0, 0, 0]:
                raise ValueError(
                    f"ROI '{name}' is not set. Run 'python src/roi_setup.py' first."
                )

        # Validate monitor
        if self.monitor_index >= len(self.sct.monitors):
            raise ValueError(
                f"Monitor index {self.monitor_index} not found. "
                f"Available monitors: 0~{len(self.sct.monitors) - 1}"
            )

    def capture_full_screen(self):
        """Capture full screen as numpy BGR array."""
        monitor = self.sct.monitors[self.monitor_index]
        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)
        # mss returns BGRA, convert to BGR
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img

    def crop_roi(self, full_image, roi_name):
        """Crop a specific ROI from the full image."""
        x, y, w, h = self.roi[roi_name]
        max_h, max_w = full_image.shape[:2]
        # Clamp to image bounds
        x = max(0, min(x, max_w - 1))
        y = max(0, min(y, max_h - 1))
        w = min(w, max_w - x)
        h = min(h, max_h - y)
        return full_image[y : y + h, x : x + w].copy()

    def capture_all_rois(self):
        """Capture screen and return all 4 ROI images."""
        full = self.capture_full_screen()
        result = {}
        for name in ["elevator_1", "panel_1", "elevator_2", "panel_2"]:
            result[name] = self.crop_roi(full, name)

        if self.save_debug:
            os.makedirs("debug", exist_ok=True)
            ts = int(time.time() * 1000)
            for name, img in result.items():
                cv2.imwrite(f"debug/{ts}_{name}.jpg", img)

        return result

    def close(self):
        """Release mss resources."""
        self.sct.close()

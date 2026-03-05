"""ROI setup tool - drag mouse to set 4 ROI regions on screen capture."""

import os
import sys
import numpy as np
import cv2
import yaml
import mss

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")

ROI_NAMES = ["elevator_1", "panel_1", "elevator_2", "panel_2"]
ROI_LABELS = [
    "Elevator Interior #1",
    "Floor Panel #1",
    "Elevator Interior #2",
    "Floor Panel #2",
]
COLORS = [
    (0, 255, 0),   # green
    (255, 0, 0),   # blue
    (0, 255, 255), # yellow
    (255, 0, 255), # magenta
]


class RoiSetup:
    def __init__(self):
        self.drawing = False
        self.start_point = None
        self.current_point = None
        self.rois = {}
        self.current_roi_index = 0
        self.base_image = None
        self.display_image = None

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_point = (x, y)
            self.current_point = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
            self.current_point = (x, y)
        elif event == cv2.EVENT_LBUTTONUP and self.drawing:
            self.drawing = False
            self.current_point = (x, y)
            x1, y1 = self.start_point
            x2, y2 = self.current_point
            roi_x = min(x1, x2)
            roi_y = min(y1, y2)
            roi_w = abs(x2 - x1)
            roi_h = abs(y2 - y1)
            if roi_w > 10 and roi_h > 10:
                name = ROI_NAMES[self.current_roi_index]
                self.rois[name] = [roi_x, roi_y, roi_w, roi_h]
                self.current_roi_index += 1

    def draw_overlay(self):
        self.display_image = self.base_image.copy()
        # Draw completed ROIs
        for i, name in enumerate(ROI_NAMES):
            if name in self.rois:
                x, y, w, h = self.rois[name]
                cv2.rectangle(self.display_image, (x, y), (x + w, y + h), COLORS[i], 2)
                cv2.putText(
                    self.display_image, ROI_LABELS[i],
                    (x + 5, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS[i], 2,
                )
        # Draw current drag
        if self.drawing and self.start_point and self.current_point:
            idx = self.current_roi_index
            if idx < len(COLORS):
                cv2.rectangle(
                    self.display_image, self.start_point, self.current_point,
                    COLORS[idx], 1,
                )
        # Status text
        if self.current_roi_index < len(ROI_NAMES):
            msg = f"Drag to set: {ROI_LABELS[self.current_roi_index]} ({self.current_roi_index + 1}/4)"
        else:
            msg = "All ROIs set! Press 's' to save, 'r' to reset, 'q' to quit"
        cv2.putText(
            self.display_image, msg,
            (10, self.display_image.shape[0] - 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2,
        )

    def save_config(self):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        for name in ROI_NAMES:
            if name in self.rois:
                config["roi"][name] = self.rois[name]
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        print(f"ROI saved to {CONFIG_PATH}")

    def run(self):
        with mss.mss() as sct:
            # Load config for monitor index
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            monitor_index = config["monitor"]["index"]
            if monitor_index >= len(sct.monitors):
                print(f"Monitor {monitor_index} not found. Using monitor 0.")
                monitor_index = 0
            monitor = sct.monitors[monitor_index]
            screenshot = sct.grab(monitor)
            self.base_image = np.array(screenshot)
            self.base_image = cv2.cvtColor(self.base_image, cv2.COLOR_BGRA2BGR)

        # Scale down for display if too large
        h, w = self.base_image.shape[:2]
        scale = 1.0
        max_display = 1200
        if w > max_display or h > max_display:
            scale = min(max_display / w, max_display / h)
            self.base_image = cv2.resize(
                self.base_image, (int(w * scale), int(h * scale))
            )

        window_name = "ROI Setup - Drag to set regions"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(window_name, self.mouse_callback)

        print("=== ROI Setup Tool ===")
        print("Drag mouse to set 4 regions in order:")
        for i, label in enumerate(ROI_LABELS):
            print(f"  {i + 1}. {label}")
        print("Keys: 'r'=reset, 's'=save, 'q'=quit")

        while True:
            self.draw_overlay()
            cv2.imshow(window_name, self.display_image)
            key = cv2.waitKey(30) & 0xFF

            if key == ord("q"):
                break
            elif key == ord("r"):
                self.rois.clear()
                self.current_roi_index = 0
                print("ROI reset.")
            elif key == ord("s"):
                if len(self.rois) == 4:
                    # If we scaled, convert coordinates back to original
                    if scale != 1.0:
                        for name in self.rois:
                            coords = self.rois[name]
                            self.rois[name] = [int(c / scale) for c in coords]
                    self.save_config()
                else:
                    print(f"Set all 4 ROIs first. Currently: {len(self.rois)}/4")

        cv2.destroyAllWindows()


if __name__ == "__main__":
    if not os.path.exists(CONFIG_PATH):
        print(f"Config file not found: {CONFIG_PATH}")
        sys.exit(1)
    setup = RoiSetup()
    setup.run()

"""Elevator CCTV Monitoring System - PyQt6 Bottom-bar GUI
   Designed to sit at the bottom of the screen over a fullscreen CCTV display.
"""

import argparse
import sys
import time
from datetime import datetime

import yaml
from loguru import logger

from src.logger import setup_logger
from src.state_machine import ElevatorStateMachine, State
from src.siren_controller import create_siren_controller

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QFrame, QSizePolicy, QSplitter,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat, QScreen


# ════════════════════════════════════════════
#  Styles
# ════════════════════════════════════════════
BG = "#0d1117"

S_MAIN = f"QMainWindow {{ background-color: {BG}; border-top: 2px solid #30363d; }}"

S_ELEV_CARD = """
    QFrame#elevCard {{
        background-color: #161b22;
        border: 1px solid {border};
        border-radius: 6px;
    }}
"""

S_SIREN_OFF = """
    QFrame#sirenBar {
        background-color: #161b22; border: 1px solid #30363d; border-radius: 6px;
    }
"""
S_SIREN_A = """
    QFrame#sirenBar {
        background-color: #b71c1c; border: 2px solid #ff5252; border-radius: 6px;
    }
"""
S_SIREN_B = """
    QFrame#sirenBar {
        background-color: #7f0000; border: 2px solid #d50000; border-radius: 6px;
    }
"""

S_BTN = """
    QPushButton {{
        background-color: {bg}; color: {fg};
        border: none; border-radius: 4px;
        padding: {pad};
        font-weight: bold; font-size: {size}px;
    }}
    QPushButton:hover {{ background-color: {hover}; }}
    QPushButton:pressed {{ background-color: {pressed}; }}
"""

S_FLOOR_IND = """
    QLabel {{
        background-color: {bg}; color: {fg};
        border-radius: 3px; padding: 2px 8px;
        font-weight: bold; font-size: 11px;
    }}
"""

S_LOG = """
    QTextEdit {
        background-color: #0d1117; color: #c9d1d9;
        border: 1px solid #30363d; border-radius: 4px;
        padding: 4px; font-family: Consolas; font-size: 10px;
    }
"""


# ════════════════════════════════════════════
#  Compact Elevator Status Widget
# ════════════════════════════════════════════
class ElevatorMini(QFrame):
    """Compact elevator panel: one horizontal row."""

    def __init__(self, elev_num, label, on_cargo, on_floor):
        super().__init__()
        self.setObjectName("elevCard")
        self.setStyleSheet(S_ELEV_CARD.format(border="#30363d"))
        self.elev_num = elev_num

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)

        # ── Title ──
        title = QLabel(label)
        title.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #00e676;")
        title.setFixedWidth(55)
        lay.addWidget(title)

        # ── State ──
        self.state_lbl = QLabel("IDLE")
        self.state_lbl.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.state_lbl.setStyleSheet("color: #8b949e;")
        self.state_lbl.setFixedWidth(120)
        lay.addWidget(self.state_lbl)

        # ── Cargo label ──
        self.cargo_lbl = QLabel("Cargo: NO")
        self.cargo_lbl.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.cargo_lbl.setStyleSheet("color: #00e676;")
        self.cargo_lbl.setFixedWidth(90)
        lay.addWidget(self.cargo_lbl)

        # ── Floor label ──
        self.floor_lbl = QLabel("Floor: -")
        self.floor_lbl.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.floor_lbl.setStyleSheet("color: #e0e0e0;")
        self.floor_lbl.setFixedWidth(68)
        lay.addWidget(self.floor_lbl)

        # ── Timer ──
        self.timer_lbl = QLabel("")
        self.timer_lbl.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.timer_lbl.setStyleSheet("color: #ffd600;")
        self.timer_lbl.setFixedWidth(50)
        lay.addWidget(self.timer_lbl)

        # ── Separator ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #30363d;")
        lay.addWidget(sep)

        # ── Cargo toggle button ──
        self.cargo_btn = QPushButton("Cargo")
        self.cargo_btn.setStyleSheet(S_BTN.format(
            bg="#37474f", fg="#b0bec5", hover="#455a64", pressed="#546e7a",
            pad="4px 10px", size=10))
        self.cargo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cargo_btn.clicked.connect(lambda: on_cargo(elev_num))
        self.cargo_btn.setFixedWidth(60)
        lay.addWidget(self.cargo_btn)

        # ── Floor buttons ──
        self.floor_btns = {}
        for f in range(1, 5):
            btn = QPushButton(f"{f}F")
            btn.setStyleSheet(S_BTN.format(
                bg="#0d47a1", fg="#fff", hover="#1565c0", pressed="#1976d2",
                pad="4px 2px", size=10))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(36)
            btn.clicked.connect(lambda _, fl=f: on_floor(elev_num, fl))
            lay.addWidget(btn)
            self.floor_btns[f] = btn

    def update_status(self, status):
        state = status["state"]
        colors = {
            "IDLE": "#8b949e",
            "CARGO_PRESENT": "#00e5ff",
            "FLOOR_ARRIVED": "#ffd600",
            "SIREN_PENDING": "#ff1744",
        }
        self.state_lbl.setText(state)
        self.state_lbl.setStyleSheet(f"color: {colors.get(state, '#8b949e')};")

        if status["cargo"]:
            self.cargo_lbl.setText("Cargo:YES")
            self.cargo_lbl.setStyleSheet("color: #ff1744; font-weight: bold;")
        else:
            self.cargo_lbl.setText("Cargo: NO")
            self.cargo_lbl.setStyleSheet("color: #00e676;")

        floor = status["floor"]
        self.floor_lbl.setText(f"Floor: {floor}F" if floor > 0 else "Floor: -")

        for f, btn in self.floor_btns.items():
            if f == floor:
                btn.setStyleSheet(S_BTN.format(
                    bg="#2979ff", fg="#fff", hover="#448aff", pressed="#2962ff",
                    pad="4px 2px", size=10))
            else:
                btn.setStyleSheet(S_BTN.format(
                    bg="#0d47a1", fg="#fff", hover="#1565c0", pressed="#1976d2",
                    pad="4px 2px", size=10))

        remaining = status["timer_remaining"]
        self.timer_lbl.setText(f"{remaining}s" if remaining > 0 else "")

        # Card border highlight
        if state == "SIREN_PENDING":
            self.setStyleSheet(S_ELEV_CARD.format(border="#ff1744"))
        elif state == "FLOOR_ARRIVED":
            self.setStyleSheet(S_ELEV_CARD.format(border="#ffd600"))
        else:
            self.setStyleSheet(S_ELEV_CARD.format(border="#30363d"))

    def set_cargo_btn(self, on):
        if on:
            self.cargo_btn.setStyleSheet(S_BTN.format(
                bg="#1b5e20", fg="#fff", hover="#2e7d32", pressed="#388e3c",
                pad="4px 10px", size=10))
        else:
            self.cargo_btn.setStyleSheet(S_BTN.format(
                bg="#37474f", fg="#b0bec5", hover="#455a64", pressed="#546e7a",
                pad="4px 10px", size=10))


# ════════════════════════════════════════════
#  Siren Alert Bar (compact)
# ════════════════════════════════════════════
class SirenBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("sirenBar")
        self.setStyleSheet(S_SIREN_OFF)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(10)

        self.alert_lbl = QLabel("Siren: All Clear")
        self.alert_lbl.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        self.alert_lbl.setStyleSheet("color: #00e676;")
        lay.addWidget(self.alert_lbl)

        self.detail_lbl = QLabel("")
        self.detail_lbl.setFont(QFont("Consolas", 11))
        self.detail_lbl.setStyleSheet("color: #e0e0e0;")
        lay.addWidget(self.detail_lbl, 1)

        # Floor indicators
        self.inds = {}
        for f in range(1, 5):
            lbl = QLabel(f" {f}F ")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(S_FLOOR_IND.format(bg="#2a2a2a", fg="#607080"))
            lay.addWidget(lbl)
            self.inds[f] = lbl

        self._blink = False

    def update_sirens(self, active):
        if active:
            self._blink = not self._blink
            self.setStyleSheet(S_SIREN_A if self._blink else S_SIREN_B)
            self.alert_lbl.setText("!! SIREN !!")
            self.alert_lbl.setStyleSheet("color: #ffffff; font-weight: bold;")

            parts = []
            for fl, eid in sorted(active.items()):
                n = eid.replace("elevator_", "")
                parts.append(f"{fl}F({n}ho)")
            self.detail_lbl.setText(" | ".join(parts))
            self.detail_lbl.setStyleSheet("color: #ffffff;")

            for f, lbl in self.inds.items():
                if f in active:
                    lbl.setStyleSheet(S_FLOOR_IND.format(bg="#d50000", fg="#fff"))
                else:
                    lbl.setStyleSheet(S_FLOOR_IND.format(bg="#2a2a2a", fg="#607080"))
        else:
            self.setStyleSheet(S_SIREN_OFF)
            self.alert_lbl.setText("Siren: All Clear")
            self.alert_lbl.setStyleSheet("color: #00e676;")
            self.detail_lbl.setText("")
            self.detail_lbl.setStyleSheet("color: #e0e0e0;")
            for lbl in self.inds.values():
                lbl.setStyleSheet(S_FLOOR_IND.format(bg="#2a2a2a", fg="#607080"))


# ════════════════════════════════════════════
#  Event Log (compact)
# ════════════════════════════════════════════
class EventLog(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setStyleSheet(S_LOG)
        self.setMaximumHeight(100)

    def add_event(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        u = msg.upper()
        if "SIREN" in u:
            color = "#ff1744"
        elif "ARRIVED" in u or "TIMER" in u:
            color = "#ffd600"
        elif "CARGO" in u:
            color = "#00e5ff"
        else:
            color = "#c9d1d9"

        cur = self.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        fmt.setFont(QFont("Consolas", 9))
        cur.insertText(f"[{ts}] {msg}\n", fmt)
        self.setTextCursor(cur)
        self.ensureCursorVisible()


# ════════════════════════════════════════════
#  Main Window — bottom bar
# ════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self, config_path="config.yaml", simulate=False):
        super().__init__()
        self.simulate = simulate

        self.config_path = config_path

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        if simulate:
            self.config["siren"]["interface"] = "dummy"

        setup_logger(config_path)

        self.capture = None
        self.inference = None

        if not simulate:
            roi_ready = all(c != [0, 0, 0, 0] for c in self.config["roi"].values())
            if roi_ready:
                self._init_capture()
            else:
                logger.warning("ROI not set yet. Use ROI Setup button.")
        else:
            self.sim_cargo = {1: False, 2: False}
            self.sim_floor = {1: 1, 2: 1}

        self.siren = create_siren_controller(self.config)
        delay = self.config["siren"]["delay_seconds"]
        self.sm1 = ElevatorStateMachine("elevator_1", self.siren, delay)
        self.sm2 = ElevatorStateMachine("elevator_2", self.siren, delay)
        self.fps = self.config["capture"]["fps"]
        self._prev_s1 = "IDLE"
        self._prev_s2 = "IDLE"
        self._prev_sirens = {}

        self._build_ui()
        self._position_bottom()
        self._start_timer()
        logger.info("GUI started (bottom-bar mode)")

    def _init_capture(self):
        """Initialize capture + inference modules (requires ROI set + models)."""
        try:
            from src.capture import ScreenCapture
            self.capture = ScreenCapture(self.config_path)
            logger.info("Capture module loaded")
        except Exception as e:
            logger.warning(f"Capture init failed: {e}")
            self.capture = None
        try:
            from src.inference import InferenceEngine
            self.inference = InferenceEngine(self.config_path)
            logger.info("Inference engine loaded")
        except Exception as e:
            logger.warning(f"Inference init failed: {e}")
            self.inference = None

    def _open_roi_setup(self):
        """Open fullscreen ROI selector overlay."""
        from src.roi_overlay import RoiOverlay
        self.hide()
        self._roi_overlay = RoiOverlay(self.config_path, on_done=self._on_roi_done)
        self._roi_overlay.show()

    def _on_roi_done(self, roi_dict):
        """Called when ROI setup is complete."""
        # Reload config
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        self.event_log.add_event("ROI settings saved!")
        for name, coords in roi_dict.items():
            self.event_log.add_event(f"  {name}: {coords}")
        logger.info(f"ROI updated: {roi_dict}")

        # Update ROI status label
        self.roi_status_lbl.setText("ROI: OK")
        self.roi_status_lbl.setStyleSheet("color: #00e676;")

        # Try to init capture if not simulate
        if not self.simulate:
            self._init_capture()

        self.show()

    # ── UI Build ──
    def _build_ui(self):
        self.setWindowTitle("Elevator CCTV Monitor")
        self.setStyleSheet(S_MAIN)
        # Frameless + always on top
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(4)

        # ── Row 0: Toolbar with ROI Setup ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        mode_lbl = QLabel("SIM" if self.simulate else "LIVE")
        mode_lbl.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        mode_lbl.setStyleSheet(
            "color: #ffd600; padding: 2px 6px;" if self.simulate
            else "color: #00e676; padding: 2px 6px;"
        )
        toolbar.addWidget(mode_lbl)

        roi_btn = QPushButton("ROI Setup")
        roi_btn.setStyleSheet(S_BTN.format(
            bg="#6a1b9a", fg="#fff", hover="#7b1fa2", pressed="#8e24aa",
            pad="3px 12px", size=10))
        roi_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        roi_btn.clicked.connect(self._open_roi_setup)
        roi_btn.setFixedWidth(90)
        toolbar.addWidget(roi_btn)

        # ROI status
        roi_ready = all(c != [0, 0, 0, 0] for c in self.config["roi"].values())
        self.roi_status_lbl = QLabel("ROI: OK" if roi_ready else "ROI: Not Set")
        self.roi_status_lbl.setFont(QFont("Consolas", 9))
        self.roi_status_lbl.setStyleSheet(
            "color: #00e676;" if roi_ready else "color: #ff1744;"
        )
        toolbar.addWidget(self.roi_status_lbl)

        toolbar.addStretch()
        root.addLayout(toolbar)

        # ── Row 1: Elevator panels ──
        self.panel1 = ElevatorMini(1, "1ho-gi", self._on_cargo, self._on_floor)
        self.panel2 = ElevatorMini(2, "2ho-gi", self._on_cargo, self._on_floor)
        root.addWidget(self.panel1)
        root.addWidget(self.panel2)

        # ── Row 2: Siren bar ──
        self.siren_bar = SirenBar()
        root.addWidget(self.siren_bar)

        # ── Row 3: Event log (collapsible) ──
        self.event_log = EventLog()
        root.addWidget(self.event_log)

        self.event_log.add_event("System started")
        if self.simulate:
            self.event_log.add_event("SIMULATION MODE")

    # ── Position at screen bottom ──
    def _position_bottom(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        w = geo.width()
        h = 260  # bar height
        self.setFixedSize(w, h)
        self.move(geo.x(), geo.y() + geo.height() - h)

    # ── Timer ──
    def _start_timer(self):
        interval = max(50, int(1000 / self.fps))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(interval)

    # ── Simulation callbacks ──
    def _on_cargo(self, num):
        self.sim_cargo[num] = not self.sim_cargo[num]
        on = self.sim_cargo[num]
        p = self.panel1 if num == 1 else self.panel2
        p.set_cargo_btn(on)
        self.event_log.add_event(f"[SIM] {num}ho-gi cargo {'ON' if on else 'OFF'}")

    def _on_floor(self, num, floor):
        self.sim_floor[num] = floor
        self.event_log.add_event(f"[SIM] {num}ho-gi -> {floor}F")

    # ── Event tracking ──
    def _track(self, sm, label, prev):
        curr = sm.state.name
        if curr != prev:
            if curr == "CARGO_PRESENT":
                self.event_log.add_event(f"{label} cargo detected (floor {sm.current_floor})")
            elif curr == "FLOOR_ARRIVED":
                self.event_log.add_event(f"{label} arrived {sm.current_floor}F - timer started")
            elif curr == "SIREN_PENDING":
                self.event_log.add_event(f"{label} {sm.current_floor}F SIREN TRIGGERED!")
            elif curr == "IDLE" and prev != "IDLE":
                self.event_log.add_event(f"{label} returned to idle")
        return curr

    # ── Main tick ──
    def _tick(self):
        if self.simulate:
            c1, c2 = self.sim_cargo[1], self.sim_cargo[2]
            f1, f2 = self.sim_floor[1], self.sim_floor[2]
        elif self.capture and self.inference:
            rois = self.capture.capture_all_rois()
            r1 = self.inference.predict_with_confirmation(
                "elevator_1", rois["elevator_1"], rois["panel_1"])
            r2 = self.inference.predict_with_confirmation(
                "elevator_2", rois["elevator_2"], rois["panel_2"])
            c1, c2 = r1["cargo_confirmed"], r2["cargo_confirmed"]
            f1, f2 = r1["floor_confirmed"], r2["floor_confirmed"]
        else:
            # No capture/inference available — skip
            return

        self.sm1.update(c1, f1)
        self.sm2.update(c2, f2)

        self.panel1.update_status(self.sm1.get_status())
        self.panel2.update_status(self.sm2.get_status())

        self._prev_s1 = self._track(self.sm1, "1ho-gi", self._prev_s1)
        self._prev_s2 = self._track(self.sm2, "2ho-gi", self._prev_s2)

        curr = self.siren.get_active_sirens()
        for fl in curr:
            if fl not in self._prev_sirens:
                n = curr[fl].replace("elevator_", "")
                self.event_log.add_event(f"** {fl}F SIREN ON ** ({n}ho-gi)")
        for fl in self._prev_sirens:
            if fl not in curr:
                self.event_log.add_event(f"{fl}F siren OFF")
        self._prev_sirens = dict(curr)
        self.siren_bar.update_sirens(curr)

    # ── Close ──
    def closeEvent(self, event):
        self._timer.stop()
        self.sm1.shutdown()
        self.sm2.shutdown()
        self.siren.close()
        if self.capture:
            self.capture.close()
        logger.info("Shutdown complete")
        event.accept()


def main():
    parser = argparse.ArgumentParser(description="Elevator CCTV Monitoring System")
    parser.add_argument("--simulate", action="store_true",
                        help="Simulation mode (no camera/model needed)")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow(config_path=args.config, simulate=args.simulate)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

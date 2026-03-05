"""Fullscreen ROI selector overlay using PyQt6.
   Captures screen, shows fullscreen, user draws 4 ROI rectangles.
"""

import os
import yaml
import numpy as np
import mss

from PyQt6.QtWidgets import QWidget, QLabel, QApplication
from PyQt6.QtCore import Qt, QRect, QPoint
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor, QFont, QBrush,
)

ROI_NAMES = ["elevator_1", "panel_1", "elevator_2", "panel_2"]
ROI_LABELS = [
    "1ho-gi Interior",
    "1ho-gi Floor Panel",
    "2ho-gi Interior",
    "2ho-gi Floor Panel",
]
ROI_GUIDE_MSG = [
    '\u201c\uc5d8\ub9ac\ubca0\uc774\ud130 1 \ub0b4\ubd80\u201d \uc601\uc5ed\uc744 \ub4dc\ub798\uadf8\ud558\uc138\uc694',
    '\u201c\uc5d8\ub9ac\ubca0\uc774\ud130 1 \uce35\uc218 \ud328\ub110\u201d \uc601\uc5ed\uc744 \ub4dc\ub798\uadf8\ud558\uc138\uc694',
    '\u201c\uc5d8\ub9ac\ubca0\uc774\ud130 2 \ub0b4\ubd80\u201d \uc601\uc5ed\uc744 \ub4dc\ub798\uadf8\ud558\uc138\uc694',
    '\u201c\uc5d8\ub9ac\ubca0\uc774\ud130 2 \uce35\uc218 \ud328\ub110\u201d \uc601\uc5ed\uc744 \ub4dc\ub798\uadf8\ud558\uc138\uc694',
]
ROI_COLORS = [
    QColor(0, 255, 0),      # green
    QColor(0, 200, 255),     # cyan
    QColor(255, 255, 0),     # yellow
    QColor(255, 0, 255),     # magenta
]


class RoiOverlay(QWidget):
    """Fullscreen overlay for selecting 4 ROI regions."""

    def __init__(self, config_path, on_done=None):
        super().__init__()
        self.config_path = config_path
        self.on_done = on_done  # callback when all ROIs set

        self.rois = {}          # name -> QRect
        self.current_index = 0
        self.drawing = False
        self.start_pos = QPoint()
        self.current_pos = QPoint()

        # Capture screen
        with mss.mss() as sct:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            mon_idx = config.get("monitor", {}).get("index", 0)
            if mon_idx >= len(sct.monitors):
                mon_idx = 0
            monitor = sct.monitors[mon_idx]
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)  # BGRA

            self.mon_x = monitor["left"]
            self.mon_y = monitor["top"]
            self.mon_w = monitor["width"]
            self.mon_h = monitor["height"]

            # Convert to QPixmap
            h, w = img.shape[:2]
            qimg = QImage(img.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
            # mss gives BGRA, QImage expects RGBA — swap B and R
            # Actually mss on Windows gives BGRA, let's convert
            img_rgb = img.copy()
            img_rgb[:, :, 0] = img[:, :, 2]  # R
            img_rgb[:, :, 2] = img[:, :, 0]  # B
            qimg = QImage(img_rgb.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
            self.bg_pixmap = QPixmap.fromImage(qimg)

        # Setup fullscreen overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setGeometry(self.mon_x, self.mon_y, self.mon_w, self.mon_h)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

    def paintEvent(self, event):
        painter = QPainter(self)

        # Background screenshot
        painter.drawPixmap(0, 0, self.bg_pixmap)

        # Dim overlay
        painter.setBrush(QBrush(QColor(0, 0, 0, 80)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(0, 0, self.width(), self.height())

        # Draw completed ROIs
        for i, name in enumerate(ROI_NAMES):
            if name in self.rois:
                rect = self.rois[name]
                pen = QPen(ROI_COLORS[i], 2)
                painter.setPen(pen)
                painter.setBrush(QBrush(QColor(ROI_COLORS[i].red(), ROI_COLORS[i].green(),
                                               ROI_COLORS[i].blue(), 40)))
                painter.drawRect(rect)
                painter.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
                painter.drawText(rect.x() + 4, rect.y() + 16, ROI_LABELS[i])

        # Draw current drag
        if self.drawing:
            rect = QRect(self.start_pos, self.current_pos).normalized()
            color = ROI_COLORS[self.current_index] if self.current_index < 4 else QColor(255, 255, 255)
            pen = QPen(color, 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 30)))
            painter.drawRect(rect)

        # ── Top center: large guide message ──
        if self.current_index < 4:
            guide = ROI_GUIDE_MSG[self.current_index]
            step = f"({self.current_index + 1} / 4)"
            color = ROI_COLORS[self.current_index]

            # Background box
            box_w, box_h = 700, 80
            box_x = (self.width() - box_w) // 2
            box_y = 30
            painter.setBrush(QBrush(QColor(0, 0, 0, 200)))
            painter.setPen(QPen(color, 2))
            painter.drawRoundedRect(box_x, box_y, box_w, box_h, 12, 12)

            # Step number
            painter.setPen(QPen(QColor(180, 180, 180)))
            painter.setFont(QFont("Consolas", 12))
            painter.drawText(box_x + 20, box_y + 24, f"STEP {step}")

            # Main guide text
            painter.setPen(QPen(color))
            painter.setFont(QFont("Malgun Gothic", 18, QFont.Weight.Bold))
            painter.drawText(box_x + 20, box_y + 60, guide)
        else:
            # All done message
            box_w, box_h = 700, 70
            box_x = (self.width() - box_w) // 2
            box_y = 30
            painter.setBrush(QBrush(QColor(0, 80, 0, 200)))
            painter.setPen(QPen(QColor(0, 255, 0), 2))
            painter.drawRoundedRect(box_x, box_y, box_w, box_h, 12, 12)

            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont("Malgun Gothic", 18, QFont.Weight.Bold))
            painter.drawText(box_x + 20, box_y + 45, "\uc124\uc815 \uc644\ub8cc! Enter\ub97c \ub204\ub974\uba74 \uc800\uc7a5\ub429\ub2c8\ub2e4")

        # ── Bottom bar: keyboard help ──
        painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(0, self.height() - 40, self.width(), 40)

        painter.setPen(QPen(QColor(160, 160, 160)))
        painter.setFont(QFont("Consolas", 11))
        painter.drawText(20, self.height() - 14, "ESC=Cancel   R=Reset   ENTER=Save")

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.current_index < 4:
            self.drawing = True
            self.start_pos = event.pos()
            self.current_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.drawing:
            self.current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            rect = QRect(self.start_pos, event.pos()).normalized()
            if rect.width() > 10 and rect.height() > 10:
                name = ROI_NAMES[self.current_index]
                self.rois[name] = rect
                self.current_index += 1
                self.update()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
        elif key == Qt.Key.Key_R:
            self.rois.clear()
            self.current_index = 0
            self.update()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if len(self.rois) == 4:
                self._save_and_close()

    def _save_and_close(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        for name, rect in self.rois.items():
            config["roi"][name] = [rect.x(), rect.y(), rect.width(), rect.height()]

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        self.close()
        if self.on_done:
            self.on_done(config["roi"])

"""Siren controller - manages relay board for floor-based sirens."""

import threading
import time
from abc import ABC, abstractmethod
from loguru import logger


RELAY_CHANNEL_MAP = {1: 1, 2: 2, 3: 3, 4: 4}


class BaseSirenController(ABC):
    @abstractmethod
    def trigger(self, elevator_id, floor):
        pass

    @abstractmethod
    def stop(self, elevator_id, floor):
        pass

    def get_active_sirens(self):
        """Return dict of currently active sirens: {floor: elevator_id}."""
        return {}

    def test_all(self):
        for floor in range(1, 5):
            logger.info(f"Testing siren channel {floor}...")
            self.trigger("test", floor)
            time.sleep(2)
            self.stop("test", floor)
            time.sleep(1)

    def close(self):
        pass


class DummySirenController(BaseSirenController):
    """Test controller - logs only, no actual signal."""

    def __init__(self, duration_seconds=5):
        self.duration = duration_seconds
        self._active_info = {}  # floor -> elevator_id
        self._lock = threading.Lock()
        logger.info("DummySirenController initialized (no actual siren)")

    def trigger(self, elevator_id, floor):
        with self._lock:
            if floor in self._active_info:
                logger.info(f"[DUMMY] Floor {floor} siren already active, skipping")
                return
            self._active_info[floor] = elevator_id
        logger.warning(f"[DUMMY SIREN ON] {elevator_id} -> Floor {floor}")

    def stop(self, elevator_id, floor):
        with self._lock:
            removed = self._active_info.pop(floor, None)
        if removed:
            logger.info(f"[DUMMY SIREN OFF] Floor {floor}")

    def get_active_sirens(self):
        with self._lock:
            return dict(self._active_info)


class UsbRelaySirenController(BaseSirenController):
    """USB relay board controller using pyserial."""

    def __init__(self, port, baud_rate=9600, duration_seconds=5):
        import serial
        self.duration = duration_seconds
        self._active_info = {}
        self._lock = threading.Lock()
        try:
            self.ser = serial.Serial(port, baud_rate, timeout=1)
            logger.info(f"USB relay connected on {port}")
        except Exception as e:
            logger.error(f"Failed to connect USB relay on {port}: {e}")
            raise

    def _send_command(self, channel, on=True):
        if on:
            cmd = bytes([0xFF, 0x01, channel, 0x00, 0x00, 0x00, 0x00, 0x00, channel])
        else:
            cmd = bytes([0xFF, 0x01, channel, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.ser.write(cmd)

    def trigger(self, elevator_id, floor):
        channel = RELAY_CHANNEL_MAP.get(floor)
        if channel is None:
            logger.error(f"No relay channel mapped for floor {floor}")
            return

        with self._lock:
            if floor in self._active_info:
                logger.info(f"Floor {floor} siren already active")
                return
            self._active_info[floor] = elevator_id

        logger.warning(f"[SIREN ON] {elevator_id} -> Floor {floor} (CH{channel})")
        self._send_command(channel, on=True)

    def stop(self, elevator_id, floor):
        channel = RELAY_CHANNEL_MAP.get(floor)
        with self._lock:
            removed = self._active_info.pop(floor, None)
        if removed and channel:
            self._send_command(channel, on=False)
            logger.info(f"[SIREN OFF] Floor {floor} (CH{channel})")

    def get_active_sirens(self):
        with self._lock:
            return dict(self._active_info)

    def close(self):
        # Turn off all channels
        for ch in RELAY_CHANNEL_MAP.values():
            try:
                self._send_command(ch, on=False)
            except Exception:
                pass
        if hasattr(self, "ser") and self.ser.is_open:
            self.ser.close()
            logger.info("USB relay port closed")


class SerialSirenController(BaseSirenController):
    """Arduino-style serial controller using JSON commands."""

    def __init__(self, port, baud_rate=9600, duration_seconds=5):
        import serial
        import json
        self.duration = duration_seconds
        self._active_info = {}
        self._lock = threading.Lock()
        self._json = json
        try:
            self.ser = serial.Serial(port, baud_rate, timeout=1)
            time.sleep(2)  # Wait for Arduino reset
            logger.info(f"Serial controller connected on {port}")
        except Exception as e:
            logger.error(f"Failed to connect serial on {port}: {e}")
            raise

    def _send_json(self, elevator_id, floor, action):
        cmd = self._json.dumps({"elevator": elevator_id, "floor": floor, "action": action})
        self.ser.write((cmd + "\n").encode())

    def trigger(self, elevator_id, floor):
        with self._lock:
            if floor in self._active_info:
                return
            self._active_info[floor] = elevator_id

        logger.warning(f"[SERIAL SIREN ON] {elevator_id} -> Floor {floor}")
        self._send_json(elevator_id, floor, "ON")

    def stop(self, elevator_id, floor):
        with self._lock:
            removed = self._active_info.pop(floor, None)
        if removed:
            self._send_json(elevator_id, floor, "OFF")
            logger.info(f"[SERIAL SIREN OFF] Floor {floor}")

    def get_active_sirens(self):
        with self._lock:
            return dict(self._active_info)

    def close(self):
        for floor in list(self._active_info):
            self.stop("shutdown", floor)
        if hasattr(self, "ser") and self.ser.is_open:
            self.ser.close()


def create_siren_controller(config):
    """Factory function to create appropriate siren controller."""
    siren_config = config["siren"]
    interface = siren_config["interface"]
    duration = siren_config["duration_seconds"]

    if interface == "dummy":
        return DummySirenController(duration)
    elif interface == "usb_relay":
        try:
            return UsbRelaySirenController(
                siren_config["port"], siren_config["baud_rate"], duration
            )
        except Exception:
            logger.warning("USB relay connection failed. Falling back to dummy controller.")
            return DummySirenController(duration)
    elif interface == "serial":
        try:
            return SerialSirenController(
                siren_config["port"], siren_config["baud_rate"], duration
            )
        except Exception:
            logger.warning("Serial connection failed. Falling back to dummy controller.")
            return DummySirenController(duration)
    else:
        logger.warning(f"Unknown siren interface '{interface}'. Using dummy controller.")
        return DummySirenController(duration)

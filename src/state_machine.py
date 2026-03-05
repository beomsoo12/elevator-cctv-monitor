"""Elevator state machine - manages state transitions per elevator."""

import threading
from enum import Enum, auto
from loguru import logger

from src.logger import (
    log_cargo_detected, log_floor_arrived,
    log_siren_triggered, log_siren_cancelled,
)


class State(Enum):
    IDLE = auto()
    CARGO_PRESENT = auto()
    FLOOR_ARRIVED = auto()
    SIREN_ACTIVE = auto()  # Siren ON, waiting for cargo removal


class ElevatorStateMachine:
    """Independent state machine for a single elevator."""

    def __init__(self, elevator_id, siren_controller, delay_seconds=10):
        self.elevator_id = elevator_id
        self.siren = siren_controller
        self.delay_seconds = delay_seconds

        self.state = State.IDLE
        self.current_floor = 0
        self.previous_floor = 0
        self._timer = None
        self._timer_start = 0
        self._lock = threading.Lock()
        self._siren_floor = 0  # Floor where siren is currently active
        self.siren_enabled = True
        self.disabled_floors = set()  # floors where siren is disabled

    def update(self, cargo_confirmed, floor_confirmed):
        """Called every frame with confirmed predictions.

        Args:
            cargo_confirmed: True/False/None (None = not yet confirmed)
            floor_confirmed: int 1-4 or None (None = not yet confirmed)
        """
        with self._lock:
            # Update floor tracking
            if floor_confirmed is not None and floor_confirmed != 0:
                if floor_confirmed != self.current_floor:
                    self.previous_floor = self.current_floor
                    self.current_floor = floor_confirmed

            if self.state == State.IDLE:
                self._handle_idle(cargo_confirmed, floor_confirmed)
            elif self.state == State.CARGO_PRESENT:
                self._handle_cargo_present(cargo_confirmed, floor_confirmed)
            elif self.state == State.FLOOR_ARRIVED:
                self._handle_floor_arrived(cargo_confirmed, floor_confirmed)
            elif self.state == State.SIREN_ACTIVE:
                self._handle_siren_active(cargo_confirmed, floor_confirmed)

    def _handle_idle(self, cargo_confirmed, floor_confirmed):
        if cargo_confirmed is True:
            self._transition(State.CARGO_PRESENT)
            log_cargo_detected(self.elevator_id, self.current_floor, 0.0)

    def _handle_cargo_present(self, cargo_confirmed, floor_confirmed):
        if cargo_confirmed is False:
            self._transition(State.IDLE)
            return

        # Check for floor change → start delay timer
        if (floor_confirmed is not None and floor_confirmed != 0
                and self.previous_floor != 0
                and floor_confirmed != self.previous_floor):
            self._transition(State.FLOOR_ARRIVED)
            log_floor_arrived(self.elevator_id, self.current_floor)
            self._start_timer()

    def _handle_floor_arrived(self, cargo_confirmed, floor_confirmed):
        if cargo_confirmed is False:
            self._cancel_timer()
            self._transition(State.IDLE)
            log_siren_cancelled(self.elevator_id, self.current_floor, "cargo removed")
            return

        # Check for another floor change (reset timer)
        if (floor_confirmed is not None and floor_confirmed != 0
                and floor_confirmed != self.current_floor):
            self._cancel_timer()
            self.previous_floor = self.current_floor
            self.current_floor = floor_confirmed
            log_floor_arrived(self.elevator_id, self.current_floor)
            self._start_timer()

    def _start_timer(self):
        import time as _time
        self._cancel_timer()
        self._timer_start = _time.time()
        self._timer = threading.Timer(self.delay_seconds, self._on_timer_expired)
        self._timer.daemon = True
        self._timer.start()
        logger.debug(f"[{self.elevator_id}] Timer started: {self.delay_seconds}s")

    def _cancel_timer(self):
        if self._timer and self._timer.is_alive():
            self._timer.cancel()
            self._timer = None
            logger.debug(f"[{self.elevator_id}] Timer cancelled")

    def _handle_siren_active(self, cargo_confirmed, floor_confirmed):
        """Siren is ON. Keep it on until cargo is removed."""
        if cargo_confirmed is False:
            # Cargo removed → turn off siren, back to IDLE
            floor = self._siren_floor
            self.siren.stop(self.elevator_id, floor)
            self._siren_floor = 0
            self._transition(State.IDLE)
            logger.info(f"[{self.elevator_id}] Siren OFF - cargo removed from {floor}F")

    def _on_timer_expired(self):
        with self._lock:
            if self.state != State.FLOOR_ARRIVED:
                return
            floor = self.current_floor

            # Check if siren is allowed
            if not self.siren_enabled or floor in self.disabled_floors:
                self._transition(State.CARGO_PRESENT)
                log_siren_cancelled(self.elevator_id, floor, "siren disabled")
                return

            self._siren_floor = floor
            self._transition(State.SIREN_ACTIVE)
            log_siren_triggered(self.elevator_id, floor)

        # Turn siren ON (stays on until cargo removed)
        self.siren.trigger(self.elevator_id, floor)

    def force_stop_siren(self):
        """Force stop siren (called when user toggles siren off)."""
        with self._lock:
            if self.state == State.SIREN_ACTIVE and self._siren_floor:
                floor = self._siren_floor
                self.siren.stop(self.elevator_id, floor)
                self._siren_floor = 0
                self._transition(State.CARGO_PRESENT)
                logger.info(f"[{self.elevator_id}] Siren force-stopped at {floor}F")
            elif self.state == State.FLOOR_ARRIVED:
                self._cancel_timer()
                self._transition(State.CARGO_PRESENT)

    def _transition(self, new_state):
        old_state = self.state
        self.state = new_state
        logger.debug(f"[{self.elevator_id}] {old_state.name} -> {new_state.name}")

    def get_status(self):
        """Return current status dict for display."""
        import time as _time
        with self._lock:
            timer_remaining = 0
            if self._timer and self._timer.is_alive() and self.state == State.FLOOR_ARRIVED:
                elapsed = _time.time() - self._timer_start
                timer_remaining = max(0, self.delay_seconds - elapsed)
            return {
                "state": self.state.name,
                "floor": self.current_floor,
                "cargo": self.state != State.IDLE,
                "timer_remaining": round(timer_remaining, 1),
                "siren_floor": self._siren_floor,
            }

    def shutdown(self):
        """Cancel timer and clean up."""
        self._cancel_timer()
        if self._siren_floor:
            self.siren.stop(self.elevator_id, self._siren_floor)
            self._siren_floor = 0
        self.state = State.IDLE

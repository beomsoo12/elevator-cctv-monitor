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
    SIREN_PENDING = auto()


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
        self._siren_fired_floor = 0  # Prevent repeat siren on same floor

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
            elif self.state == State.SIREN_PENDING:
                pass  # Waiting for siren to complete

    def _handle_idle(self, cargo_confirmed, floor_confirmed):
        if cargo_confirmed is True:
            self._transition(State.CARGO_PRESENT)
            log_cargo_detected(self.elevator_id, self.current_floor, 0.0)
        # Reset siren-fired tracking when floor changes while idle
        if (floor_confirmed is not None and floor_confirmed != 0
                and floor_confirmed != self._siren_fired_floor):
            self._siren_fired_floor = 0

    def _handle_cargo_present(self, cargo_confirmed, floor_confirmed):
        if cargo_confirmed is False:
            self._transition(State.IDLE)
            return

        # Check for floor change (skip if siren already fired on this floor)
        if (floor_confirmed is not None and floor_confirmed != 0
                and self.previous_floor != 0
                and floor_confirmed != self.previous_floor
                and floor_confirmed != self._siren_fired_floor):
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

    def _on_timer_expired(self):
        with self._lock:
            if self.state != State.FLOOR_ARRIVED:
                return
            self._transition(State.SIREN_PENDING)
            floor = self.current_floor
            self._siren_fired_floor = floor  # Remember: siren already fired here
            log_siren_triggered(self.elevator_id, floor)

        # Trigger siren (runs in its own thread)
        self.siren.trigger(self.elevator_id, floor)

        with self._lock:
            self._transition(State.IDLE)

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
            }

    def shutdown(self):
        """Cancel timer and clean up."""
        self._cancel_timer()
        self.state = State.IDLE

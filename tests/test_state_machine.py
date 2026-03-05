"""Unit tests for elevator state machine."""

import sys
import os
import time
import threading
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.state_machine import ElevatorStateMachine, State


@pytest.fixture
def mock_siren():
    siren = MagicMock()
    return siren


@pytest.fixture
def sm(mock_siren):
    return ElevatorStateMachine("elevator_1", mock_siren, delay_seconds=1)


class TestStateMachine:
    def test_initial_state(self, sm):
        assert sm.state == State.IDLE

    def test_idle_to_cargo_present(self, sm):
        sm.update(cargo_confirmed=True, floor_confirmed=1)
        assert sm.state == State.CARGO_PRESENT

    def test_cargo_present_to_idle_on_cargo_removed(self, sm):
        sm.update(cargo_confirmed=True, floor_confirmed=1)
        assert sm.state == State.CARGO_PRESENT
        sm.update(cargo_confirmed=False, floor_confirmed=1)
        assert sm.state == State.IDLE

    def test_cargo_present_to_floor_arrived(self, sm):
        # First set initial floor
        sm.current_floor = 1
        sm.previous_floor = 1
        sm.state = State.CARGO_PRESENT

        # Floor changes from 1 to 3
        sm.update(cargo_confirmed=True, floor_confirmed=3)
        assert sm.state == State.FLOOR_ARRIVED

    def test_floor_arrived_cargo_removed_cancels_timer(self, sm):
        sm.current_floor = 1
        sm.previous_floor = 1
        sm.state = State.CARGO_PRESENT

        sm.update(cargo_confirmed=True, floor_confirmed=3)
        assert sm.state == State.FLOOR_ARRIVED

        sm.update(cargo_confirmed=False, floor_confirmed=3)
        assert sm.state == State.IDLE

    def test_siren_triggered_after_delay(self, sm, mock_siren):
        sm.current_floor = 1
        sm.previous_floor = 1
        sm.state = State.CARGO_PRESENT

        sm.update(cargo_confirmed=True, floor_confirmed=3)
        assert sm.state == State.FLOOR_ARRIVED

        # Wait for timer to expire (delay_seconds=1)
        time.sleep(1.5)

        # Siren should have been triggered and stay active
        mock_siren.trigger.assert_called_once_with("elevator_1", 3)
        assert sm.state == State.SIREN_ACTIVE

    def test_siren_off_when_cargo_removed(self, sm, mock_siren):
        sm.current_floor = 1
        sm.previous_floor = 1
        sm.state = State.CARGO_PRESENT

        sm.update(cargo_confirmed=True, floor_confirmed=3)
        time.sleep(1.5)
        assert sm.state == State.SIREN_ACTIVE

        # Cargo removed → siren should stop
        sm.update(cargo_confirmed=False, floor_confirmed=3)
        assert sm.state == State.IDLE
        mock_siren.stop.assert_called_once_with("elevator_1", 3)

    def test_siren_stays_on_while_cargo_present(self, sm, mock_siren):
        sm.current_floor = 1
        sm.previous_floor = 1
        sm.state = State.CARGO_PRESENT

        sm.update(cargo_confirmed=True, floor_confirmed=3)
        time.sleep(1.5)
        assert sm.state == State.SIREN_ACTIVE

        # Cargo still present → siren stays on
        sm.update(cargo_confirmed=True, floor_confirmed=3)
        assert sm.state == State.SIREN_ACTIVE
        mock_siren.stop.assert_not_called()

    def test_none_cargo_no_transition(self, sm):
        sm.update(cargo_confirmed=None, floor_confirmed=1)
        assert sm.state == State.IDLE

    def test_two_elevators_independent(self, mock_siren):
        sm1 = ElevatorStateMachine("elevator_1", mock_siren, delay_seconds=1)
        sm2 = ElevatorStateMachine("elevator_2", mock_siren, delay_seconds=1)

        sm1.update(cargo_confirmed=True, floor_confirmed=1)
        assert sm1.state == State.CARGO_PRESENT
        assert sm2.state == State.IDLE

        sm2.update(cargo_confirmed=True, floor_confirmed=2)
        assert sm2.state == State.CARGO_PRESENT

    def test_shutdown_cancels_timer(self, sm):
        sm.current_floor = 1
        sm.previous_floor = 1
        sm.state = State.CARGO_PRESENT

        sm.update(cargo_confirmed=True, floor_confirmed=3)
        assert sm.state == State.FLOOR_ARRIVED

        sm.shutdown()
        assert sm.state == State.IDLE

    def test_get_status(self, sm):
        status = sm.get_status()
        assert status["state"] == "IDLE"
        assert status["floor"] == 0
        assert status["cargo"] is False

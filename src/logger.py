"""Event logger module using loguru."""

import os
import sys
import yaml
from loguru import logger


def setup_logger(config_path="config.yaml"):
    """Initialize logger from config."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    log_config = config.get("logging", {})
    level = log_config.get("level", "INFO")
    log_file = log_config.get("file", "logs/events.log")
    max_size_mb = log_config.get("max_size_mb", 10)

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger.remove()

    # Console with colors
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        colorize=True,
    )

    # File with rotation
    logger.add(
        log_file,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        rotation=f"{max_size_mb} MB",
        retention="30 days",
        encoding="utf-8",
    )

    logger.info("Logger initialized")
    return logger


def log_cargo_detected(elevator_id, floor, confidence):
    logger.info(f"[{elevator_id}] Cargo detected at floor {floor} (confidence: {confidence:.2f})")


def log_floor_arrived(elevator_id, floor):
    logger.info(f"[{elevator_id}] Arrived at floor {floor}")


def log_siren_triggered(elevator_id, floor):
    logger.warning(f"[{elevator_id}] SIREN TRIGGERED at floor {floor}")


def log_siren_cancelled(elevator_id, floor, reason):
    logger.info(f"[{elevator_id}] Siren cancelled at floor {floor}: {reason}")


def log_model_prediction(elevator_id, cargo_result, floor_result):
    cargo_str = f"cargo={'loaded' if cargo_result['is_loaded'] else 'empty'}({cargo_result['confidence']:.2f})"
    floor_str = f"floor={floor_result['floor']}({floor_result['confidence']:.2f})"
    logger.debug(f"[{elevator_id}] Prediction: {cargo_str}, {floor_str}")

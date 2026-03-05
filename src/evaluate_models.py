"""Evaluate trained models - metrics and single image prediction."""

import argparse
import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from sklearn.metrics import (
    classification_report, confusion_matrix, ConfusionMatrixDisplay,
    accuracy_score, precision_score, recall_score, f1_score,
)
import cv2

CARGO_MODEL_PATH = "models/cargo_model.keras"
FLOOR_MODEL_PATH = "models/floor_model.keras"
CARGO_DATASET = "dataset/cargo"
FLOOR_DATASET = "dataset/floor"
INPUT_SIZE = (224, 224)
BATCH_SIZE = 16


def evaluate_cargo():
    print("=== Cargo Detection Model Evaluation ===")
    if not os.path.exists(CARGO_MODEL_PATH):
        print(f"Model not found: {CARGO_MODEL_PATH}")
        return

    model = tf.keras.models.load_model(CARGO_MODEL_PATH)
    datagen = ImageDataGenerator(rescale=1.0 / 255, validation_split=0.2)
    val_gen = datagen.flow_from_directory(
        CARGO_DATASET, target_size=INPUT_SIZE, batch_size=BATCH_SIZE,
        class_mode="binary", subset="validation",
        classes=["empty", "loaded"], shuffle=False,
    )

    predictions = model.predict(val_gen)
    y_pred = (predictions.flatten() > 0.5).astype(int)
    y_true = val_gen.classes

    print(f"  Accuracy:  {accuracy_score(y_true, y_pred):.4f}")
    print(f"  Precision: {precision_score(y_true, y_pred, zero_division=0):.4f}")
    print(f"  Recall:    {recall_score(y_true, y_pred, zero_division=0):.4f}")
    print(f"  F1 Score:  {f1_score(y_true, y_pred, zero_division=0):.4f}")

    cm = confusion_matrix(y_true, y_pred)
    disp = ConfusionMatrixDisplay(cm, display_labels=["empty", "loaded"])
    fig, ax = plt.subplots(figsize=(6, 6))
    disp.plot(ax=ax, cmap="Blues")
    ax.set_title("Cargo Model - Confusion Matrix")
    plt.tight_layout()
    save_path = "models/training_history/cargo_confusion_matrix.png"
    plt.savefig(save_path, dpi=100)
    plt.close()
    print(f"  Confusion matrix saved: {save_path}")


def evaluate_floor():
    print("\n=== Floor Recognition Model Evaluation ===")
    if not os.path.exists(FLOOR_MODEL_PATH):
        print(f"Model not found: {FLOOR_MODEL_PATH}")
        return

    model = tf.keras.models.load_model(FLOOR_MODEL_PATH)
    datagen = ImageDataGenerator(rescale=1.0 / 255, validation_split=0.2)
    val_gen = datagen.flow_from_directory(
        FLOOR_DATASET, target_size=INPUT_SIZE, batch_size=BATCH_SIZE,
        class_mode="categorical", subset="validation",
        classes=["floor_1", "floor_2", "floor_3", "floor_4"], shuffle=False,
    )

    predictions = model.predict(val_gen)
    y_pred = np.argmax(predictions, axis=1)
    y_true = val_gen.classes

    print(f"  Overall Accuracy: {accuracy_score(y_true, y_pred):.4f}")
    print(classification_report(y_true, y_pred, target_names=["1F", "2F", "3F", "4F"], zero_division=0))


def predict_single(image_path, model_type):
    """Predict a single image."""
    if model_type == "cargo":
        if not os.path.exists(CARGO_MODEL_PATH):
            print(f"Model not found: {CARGO_MODEL_PATH}")
            return
        model = tf.keras.models.load_model(CARGO_MODEL_PATH)
        img = cv2.imread(image_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, INPUT_SIZE)
        img = img.astype(np.float32) / 255.0
        img = np.expand_dims(img, axis=0)
        pred = model.predict(img, verbose=0)[0][0]
        label = "loaded" if pred > 0.5 else "empty"
        print(f"  Prediction: {label} (score: {pred:.4f})")
    elif model_type == "floor":
        if not os.path.exists(FLOOR_MODEL_PATH):
            print(f"Model not found: {FLOOR_MODEL_PATH}")
            return
        model = tf.keras.models.load_model(FLOOR_MODEL_PATH)
        img = cv2.imread(image_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, INPUT_SIZE)
        img = img.astype(np.float32) / 255.0
        img = np.expand_dims(img, axis=0)
        pred = model.predict(img, verbose=0)[0]
        floor = np.argmax(pred) + 1
        print(f"  Prediction: Floor {floor}")
        for i, p in enumerate(pred):
            print(f"    Floor {i + 1}: {p:.4f}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate models")
    parser.add_argument("--image", help="Single image path for prediction")
    parser.add_argument("--model", choices=["cargo", "floor"],
                        help="Model type for single prediction")
    args = parser.parse_args()

    if args.image and args.model:
        if not os.path.exists(args.image):
            print(f"Image not found: {args.image}")
            sys.exit(1)
        predict_single(args.image, args.model)
    else:
        evaluate_cargo()
        evaluate_floor()


if __name__ == "__main__":
    main()

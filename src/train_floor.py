"""Train floor recognition model (4-class: floor 1~4)."""

import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, Dropout, GlobalAveragePooling2D
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay

DATASET_DIR = "dataset/floor"
MODEL_PATH = "models/floor_model.keras"
HISTORY_DIR = "models/training_history"
INPUT_SIZE = (224, 224)
BATCH_SIZE = 16
NUM_CLASSES = 4
TARGET_ACCURACY = 0.95


def create_model():
    base_model = MobileNetV2(weights="imagenet", include_top=False, input_shape=(*INPUT_SIZE, 3))
    base_model.trainable = False

    x = base_model.output
    x = GlobalAveragePooling2D()(x)
    x = Dense(256, activation="relu")(x)
    x = Dropout(0.3)(x)
    output = Dense(NUM_CLASSES, activation="softmax")(x)

    model = Model(inputs=base_model.input, outputs=output)
    return model, base_model


def get_data_generators():
    train_datagen = ImageDataGenerator(
        rescale=1.0 / 255,
        rotation_range=15,
        width_shift_range=0.1,
        height_shift_range=0.1,
        brightness_range=[0.7, 1.3],
        horizontal_flip=False,  # Floor numbers shouldn't be flipped
        zoom_range=0.1,
        validation_split=0.2,
    )

    train_gen = train_datagen.flow_from_directory(
        DATASET_DIR,
        target_size=INPUT_SIZE,
        batch_size=BATCH_SIZE,
        class_mode="categorical",
        subset="training",
        classes=["floor_1", "floor_2", "floor_3", "floor_4"],
    )

    val_gen = train_datagen.flow_from_directory(
        DATASET_DIR,
        target_size=INPUT_SIZE,
        batch_size=BATCH_SIZE,
        class_mode="categorical",
        subset="validation",
        classes=["floor_1", "floor_2", "floor_3", "floor_4"],
        shuffle=False,
    )

    return train_gen, val_gen


def plot_history(history, save_path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    ax1.plot(history.history["accuracy"], label="Train")
    ax1.plot(history.history["val_accuracy"], label="Validation")
    ax1.set_title("Floor Model - Accuracy")
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Accuracy")
    ax1.legend()

    ax2.plot(history.history["loss"], label="Train")
    ax2.plot(history.history["val_loss"], label="Validation")
    ax2.set_title("Floor Model - Loss")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Loss")
    ax2.legend()

    plt.tight_layout()
    plt.savefig(save_path, dpi=100)
    plt.close()


def plot_confusion_matrix(model, val_gen, save_path):
    val_gen.reset()
    predictions = model.predict(val_gen)
    y_pred = np.argmax(predictions, axis=1)
    y_true = val_gen.classes

    cm = confusion_matrix(y_true, y_pred)
    disp = ConfusionMatrixDisplay(cm, display_labels=["1F", "2F", "3F", "4F"])
    fig, ax = plt.subplots(figsize=(6, 6))
    disp.plot(ax=ax, cmap="Blues")
    ax.set_title("Floor Model - Confusion Matrix")
    plt.tight_layout()
    plt.savefig(save_path, dpi=100)
    plt.close()
    print(f"Confusion matrix saved: {save_path}")

    # Per-class accuracy
    for i in range(NUM_CLASSES):
        if cm[i].sum() > 0:
            acc = cm[i][i] / cm[i].sum()
            print(f"  Floor {i + 1}: {acc:.1%}")


def main():
    # Check dataset
    for i in range(1, 5):
        path = os.path.join(DATASET_DIR, f"floor_{i}")
        if not os.path.exists(path):
            print(f"ERROR: Dataset directory not found: {path}")
            sys.exit(1)
        count = len([f for f in os.listdir(path) if f.lower().endswith((".jpg", ".png", ".jpeg"))])
        print(f"  floor_{i}: {count} images")
        if count < 10:
            print(f"WARNING: Very few images for floor_{i}. Recommend at least 100.")

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)

    print("\n=== Phase 1: Feature Extraction ===")
    model, base_model = create_model()
    model.compile(
        optimizer=Adam(learning_rate=1e-3),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )

    train_gen, val_gen = get_data_generators()

    callbacks = [
        EarlyStopping(patience=5, restore_best_weights=True),
        ModelCheckpoint(MODEL_PATH, save_best_only=True, monitor="val_accuracy"),
    ]

    history1 = model.fit(
        train_gen, validation_data=val_gen,
        epochs=10, callbacks=callbacks,
    )

    print("\n=== Phase 2: Fine Tuning ===")
    base_model.trainable = True
    for layer in base_model.layers[:-30]:
        layer.trainable = False

    model.compile(
        optimizer=Adam(learning_rate=1e-5),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )

    history2 = model.fit(
        train_gen, validation_data=val_gen,
        epochs=20, callbacks=callbacks,
    )

    # Combine histories
    combined = {}
    for key in history1.history:
        combined[key] = history1.history[key] + history2.history[key]

    class CombinedHistory:
        pass
    ch = CombinedHistory()
    ch.history = combined

    plot_history(ch, os.path.join(HISTORY_DIR, "floor_history.png"))

    # Confusion matrix
    print("\n=== Per-Class Accuracy ===")
    plot_confusion_matrix(model, val_gen, os.path.join(HISTORY_DIR, "floor_confusion_matrix.png"))

    # Final evaluation
    val_loss, val_acc = model.evaluate(val_gen)
    print(f"\nFinal Validation Accuracy: {val_acc:.4f}")

    if val_acc < TARGET_ACCURACY:
        print(f"WARNING: Accuracy {val_acc:.4f} is below target {TARGET_ACCURACY}.")
    else:
        print("Target accuracy reached!")

    model.save(MODEL_PATH)
    print(f"Model saved: {MODEL_PATH}")


if __name__ == "__main__":
    main()

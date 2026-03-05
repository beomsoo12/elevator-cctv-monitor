"""Data collection tool for training dataset."""

import argparse
import os
import sys
import time
import numpy as np
import cv2

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.capture import ScreenCapture


def compute_similarity(img1, img2):
    """Compute pixel similarity between two images (0~1)."""
    if img1 is None or img2 is None:
        return 0.0
    if img1.shape != img2.shape:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
    diff = cv2.absdiff(img1, img2)
    return 1.0 - (np.mean(diff) / 255.0)


def main():
    parser = argparse.ArgumentParser(description="Collect training data")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--class", dest="cls", choices=["empty", "loaded"],
                       help="Cargo class to collect")
    group.add_argument("--floor", type=int, choices=[1, 2, 3, 4],
                       help="Floor number to collect")
    parser.add_argument("--elevator", type=int, required=True, choices=[1, 2],
                        help="Elevator number")
    parser.add_argument("--interval", type=float, default=0.5,
                        help="Capture interval in seconds")
    parser.add_argument("--target", type=int, default=300,
                        help="Target number of images")
    args = parser.parse_args()

    # Determine save path and ROI name
    if args.cls:
        save_dir = os.path.join("dataset", "cargo", args.cls)
        roi_name = f"elevator_{args.elevator}"
        print(f"Collecting: cargo/{args.cls} from elevator_{args.elevator}")
    else:
        save_dir = os.path.join("dataset", "floor", f"floor_{args.floor}")
        roi_name = f"panel_{args.elevator}"
        print(f"Collecting: floor_{args.floor} from panel_{args.elevator}")

    os.makedirs(save_dir, exist_ok=True)
    existing = len([f for f in os.listdir(save_dir) if f.endswith(".jpg")])
    print(f"Existing images: {existing}")

    try:
        capture = ScreenCapture("config.yaml")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    prev_img = None
    count = existing
    similarity_threshold = 0.98

    print(f"Target: {args.target} images, Interval: {args.interval}s")
    print("Press 'q' in the preview window to stop.")

    cv2.namedWindow("Preview", cv2.WINDOW_NORMAL)

    try:
        while count < args.target:
            rois = capture.capture_all_rois()
            img = rois[roi_name]

            # Check similarity
            sim = compute_similarity(prev_img, img)
            if sim > similarity_threshold:
                cv2.imshow("Preview", img)
                if cv2.waitKey(int(args.interval * 1000)) & 0xFF == ord("q"):
                    break
                continue

            # Save
            filename = f"{int(time.time() * 1000)}_{count:04d}.jpg"
            filepath = os.path.join(save_dir, filename)
            cv2.imwrite(filepath, img)
            prev_img = img.copy()
            count += 1

            # Display progress
            progress = count / args.target * 100
            print(f"\r[{progress:5.1f}%] {count}/{args.target} saved", end="", flush=True)

            cv2.imshow("Preview", img)
            if cv2.waitKey(int(args.interval * 1000)) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        pass
    finally:
        capture.close()
        cv2.destroyAllWindows()
        print(f"\nDone. Total images: {count}")


if __name__ == "__main__":
    main()

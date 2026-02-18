"""Download OmniParser V2 models from HuggingFace.

Run this once before starting the server:
    python download_models.py

Downloads:
    - YOLO icon detection model (~40 MB)
    - Florence-2 caption model (~1.08 GB)
"""

import os
import sys


def main():
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("ERROR: huggingface_hub not installed. Run: pip install huggingface_hub")
        sys.exit(1)

    models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    os.makedirs(models_dir, exist_ok=True)

    repo_id = "microsoft/OmniParser-v2.0"

    print(f"Downloading OmniParser V2 models to {models_dir}...")
    print(f"Repository: {repo_id}")
    print()

    # Download icon detection model (YOLO, ~40 MB)
    print("[1/2] Downloading icon detection model (YOLO, ~40 MB)...")
    snapshot_download(
        repo_id=repo_id,
        allow_patterns=["icon_detect/*"],
        local_dir=models_dir,
    )
    print("      Done.")

    # Download icon caption model (Florence-2, ~1.08 GB)
    print("[2/2] Downloading icon caption model (Florence-2, ~1.08 GB)...")
    snapshot_download(
        repo_id=repo_id,
        allow_patterns=["icon_caption/*"],
        local_dir=models_dir,
    )
    print("      Done.")

    # Verify files exist
    yolo_path = os.path.join(models_dir, "icon_detect", "model.pt")
    florence_dir = os.path.join(models_dir, "icon_caption")

    if os.path.exists(yolo_path):
        size_mb = os.path.getsize(yolo_path) / (1024 * 1024)
        print(f"\n  YOLO model: {yolo_path} ({size_mb:.1f} MB)")
    else:
        print(f"\n  WARNING: YOLO model not found at {yolo_path}")

    if os.path.isdir(florence_dir):
        total = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, _, fns in os.walk(florence_dir)
            for f in fns
        )
        print(f"  Florence-2: {florence_dir} ({total / (1024**2):.1f} MB)")
    else:
        print(f"  WARNING: Florence-2 model not found at {florence_dir}")

    print("\nModels ready. Start the server with: python server.py")


if __name__ == "__main__":
    main()

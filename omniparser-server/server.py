"""OmniParser Vision Server — HTTP wrapper for YOLO + Florence-2 element detection.

Accepts screenshots, returns structured UI element data in Nexus format.

Usage:
    python server.py                          # CPU, port 8500
    python server.py --device cuda            # GPU
    python server.py --port 9000 --device cuda

Requires models downloaded first: python download_models.py
"""

import argparse
import base64
import io
import os
import sys
import time

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

# Add OmniParser's util/ to path if cloned alongside
# The server imports OmniParser's internal functions directly
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(SCRIPT_DIR, "models")

# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

_yolo_model = None
_caption_model_processor = None
_device = "cpu"


def _check_models_exist():
    yolo_path = os.path.join(MODELS_DIR, "icon_detect", "model.pt")
    caption_dir = os.path.join(MODELS_DIR, "icon_caption")
    missing = []
    if not os.path.exists(yolo_path):
        missing.append(f"YOLO model: {yolo_path}")
    if not os.path.isdir(caption_dir):
        missing.append(f"Florence-2 model: {caption_dir}")
    if missing:
        print("ERROR: Models not found. Run 'python download_models.py' first.")
        for m in missing:
            print(f"  Missing: {m}")
        sys.exit(1)


def _load_models(device: str):
    """Load YOLO and Florence-2 models. Called once at startup."""
    global _yolo_model, _caption_model_processor, _device
    _device = device

    from omni_utils import get_yolo_model

    print(f"Loading YOLO model from {MODELS_DIR}/icon_detect/model.pt ...")
    _yolo_model = get_yolo_model(
        model_path=os.path.join(MODELS_DIR, "icon_detect", "model.pt")
    )

    # Load Florence-2 directly instead of using OmniParser's get_caption_model_processor.
    # Reason: OmniParser loads the processor from "microsoft/Florence-2-base" via
    # trust_remote_code=True, which downloads the latest processing_florence2.py from
    # HuggingFace. That code is incompatible with tokenizers>=0.20. We load from our
    # local patched copy instead.
    import torch
    from transformers import AutoProcessor, AutoModelForCausalLM

    florence2_base_dir = os.path.join(MODELS_DIR, "florence2_base")
    icon_caption_dir = os.path.join(MODELS_DIR, "icon_caption")

    print(f"Loading Florence-2 processor from {florence2_base_dir} ...")
    processor = AutoProcessor.from_pretrained(florence2_base_dir, trust_remote_code=True)

    print(f"Loading Florence-2 model (device={device}) ...")
    dtype = torch.float32 if device == "cpu" else torch.float16
    model = AutoModelForCausalLM.from_pretrained(
        icon_caption_dir, torch_dtype=dtype, trust_remote_code=True
    ).to(device)

    _caption_model_processor = {"model": model, "processor": processor}
    print("Models loaded.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="OmniParser Vision Server")


class DetectRequest(BaseModel):
    image: str  # base64-encoded PNG/JPG
    box_threshold: float = 0.05
    iou_threshold: float = 0.1
    annotated: bool = False


@app.get("/health")
def health():
    return {
        "ok": True,
        "models_loaded": _yolo_model is not None,
        "device": _device,
    }


@app.post("/detect")
def detect(req: DetectRequest):
    from PIL import Image
    from omni_utils import check_ocr_box, get_som_labeled_img

    t0 = time.time()

    # Decode image
    img_bytes = base64.b64decode(req.image)
    image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img_w, img_h = image.size

    # OCR pass (text detection)
    (ocr_texts, ocr_bboxes), _ = check_ocr_box(
        image,
        display_img=False,
        output_bb_format="xyxy",
        easyocr_args={"text_threshold": 0.8},
        use_paddleocr=False,
    )

    # Scaling config for annotation
    box_overlay_ratio = max(img_w, img_h) / 3200
    draw_bbox_config = {
        "text_scale": 0.8 * box_overlay_ratio,
        "text_thickness": max(int(2 * box_overlay_ratio), 1),
        "text_padding": max(int(3 * box_overlay_ratio), 1),
        "thickness": max(int(3 * box_overlay_ratio), 1),
    }

    # Run OmniParser (YOLO detection + Florence-2 captioning)
    encoded_image, label_coordinates, filtered_boxes_elem = get_som_labeled_img(
        image,
        _yolo_model,
        BOX_TRESHOLD=req.box_threshold,
        output_coord_in_ratio=True,
        ocr_bbox=ocr_bboxes,
        draw_bbox_config=draw_bbox_config,
        caption_model_processor=_caption_model_processor,
        ocr_text=ocr_texts,
        use_local_semantics=True,
        iou_threshold=req.iou_threshold,
        scale_img=False,
        batch_size=128,
    )

    latency = time.time() - t0

    # Normalize to Nexus element format
    # filtered_boxes_elem: list of {'type': 'text'|'icon', 'bbox': [x1,y1,x2,y2], 'interactivity': bool, 'content': str}
    # bbox values are in ratio (0-1) when output_coord_in_ratio=True
    elements = []
    for i, elem in enumerate(filtered_boxes_elem):
        bbox = elem["bbox"]  # [x1, y1, x2, y2] normalized 0-1
        x = int(bbox[0] * img_w)
        y = int(bbox[1] * img_h)
        x2 = int(bbox[2] * img_w)
        y2 = int(bbox[3] * img_h)
        w = x2 - x
        h = y2 - y

        elements.append({
            "id": i,
            "name": elem.get("content", "") or "",
            "type": elem.get("type", "unknown"),
            "bounds": {
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "center_x": x + w // 2,
                "center_y": y + h // 2,
            },
            "interactivity": elem.get("interactivity", False),
            "source": "omniparser",
        })

    response = {
        "ok": True,
        "elements": elements,
        "count": len(elements),
        "latency": round(latency, 3),
        "image_size": {"width": img_w, "height": img_h},
    }

    # Optionally include the annotated image (Set-of-Mark style)
    if req.annotated:
        response["annotated_image"] = encoded_image

    return response


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import torch

    parser = argparse.ArgumentParser(description="OmniParser Vision Server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("OMNIPARSER_PORT", "8500")))
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu",
                        choices=["cpu", "cuda"], help="Inference device (auto-detects GPU)")
    args = parser.parse_args()

    _check_models_exist()
    _load_models(args.device)

    print(f"\nStarting OmniParser server on http://{args.host}:{args.port}")
    print(f"  Device: {args.device}")
    print(f"  POST /detect  — parse screenshot")
    print(f"  GET  /health  — check status\n")

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

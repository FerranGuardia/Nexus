# OmniParser Vision Server

HTTP server wrapping Microsoft's OmniParser V2 (YOLO-v8 + Florence-2) for UI element detection from screenshots.

Runs as a separate service from Nexus — different venv, different process. Nexus calls it over HTTP.

## Setup

```bash
cd omniparser-server

# 1. Create a separate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux

# 2. Install PyTorch (pick one)
# GPU (CUDA 12.x):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
# CPU only:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 3. Install remaining dependencies
pip install -r requirements.txt

# 4. Clone OmniParser source (for util/ imports)
python setup.py

# 5. Download models (~1.1 GB total)
python download_models.py

# 6. Start the server
python server.py                # auto-detects GPU/CPU, port 8500
python server.py --device cuda  # force GPU
python server.py --port 9000    # custom port
```

## API

### `GET /health`
Check server status.

```json
{"ok": true, "models_loaded": true, "device": "cuda"}
```

### `POST /detect`
Parse a screenshot for UI elements.

**Request:**
```json
{
  "image": "<base64 PNG>",
  "box_threshold": 0.05,
  "iou_threshold": 0.1,
  "annotated": false
}
```

**Response:**
```json
{
  "ok": true,
  "elements": [
    {
      "id": 0,
      "name": "Search",
      "type": "text",
      "bounds": {"x": 100, "y": 50, "width": 200, "height": 30, "center_x": 200, "center_y": 65},
      "interactivity": false,
      "source": "omniparser"
    }
  ],
  "count": 15,
  "latency": 0.823,
  "image_size": {"width": 1920, "height": 1080}
}
```

When `annotated: true`, response includes `"annotated_image": "<base64 PNG>"` with numbered bounding boxes drawn on the screenshot.

## Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `OMNIPARSER_PORT` | 8500 | Server port |
| `PYTHONIOENCODING` | (system) | Set to `utf-8` on Windows to avoid EasyOCR progress bar encoding errors |

## Performance

| Device | Latency |
|--------|---------|
| A100 | ~0.6s |
| RTX 4090 | ~0.8s |
| CPU | ~5-15s |

First inference after startup includes model warmup — subsequent calls are faster.

## Troubleshooting

### `TokenizersBackend has no attribute additional_special_tokens`
The HuggingFace-hosted `processing_florence2.py` is incompatible with `tokenizers>=0.20`. The server loads from `models/florence2_base/` (patched locally) to avoid this. If the error reappears:
1. Delete the HF cache: `~/.cache/huggingface/modules/transformers_modules/microsoft/Florence*`
2. Ensure `transformers==4.45.2` is installed (not newer)
3. Verify `models/florence2_base/processing_florence2.py` has the `getattr` fix on line 89

### `openai.__spec__ is None`
The `openai` package must be genuinely installed (not stubbed). OmniParser's utils.py imports it, and transformers uses `importlib.util.find_spec("openai")` which crashes on stub modules with no `__spec__`.

### `UnicodeEncodeError` from EasyOCR
Set `PYTHONIOENCODING=utf-8` before starting the server. EasyOCR uses Unicode block characters in progress bars that Windows cp1252 can't encode.

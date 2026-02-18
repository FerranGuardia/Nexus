"""Import shim for OmniParser's util module.

Adds the cloned OmniParser repo to sys.path and stubs out paddleocr
(~500MB dep we don't need) before importing util.utils.
"""

import os
import sys
import types

# Add cloned OmniParser to path
_omniparser_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "OmniParser")
if _omniparser_dir not in sys.path:
    sys.path.insert(0, _omniparser_dir)

# Stub out paddleocr before importing utils.py — it's a top-level import
# that initializes PaddleOCR on import. We use easyocr instead (use_paddleocr=False).
if "paddleocr" not in sys.modules:
    _stub = types.ModuleType("paddleocr")
    _stub.PaddleOCR = lambda **kwargs: None  # dummy constructor
    sys.modules["paddleocr"] = _stub

# Now safe to import (openai is installed as a real package)
from util.utils import (  # noqa: E402
    get_som_labeled_img,
    get_caption_model_processor,
    get_yolo_model,
    check_ocr_box,
)

__all__ = [
    "get_som_labeled_img",
    "get_caption_model_processor",
    "get_yolo_model",
    "check_ocr_box",
]

"""
PDF document reading and form filling tools.
Three document types, detected by _detect_path():
  - 'acroform' : digital PDF with embedded interactive widget fields
  - 'digital'  : plain digital PDF with machine-readable text but no widgets (e.g. resume, report)
  - 'scanned'  : photo/scan — no extractable text, needs OCR (Phases 3–6)
"""

import os
import fitz  # pymupdf
from PIL import Image, ImageFilter

# Cache of scanned field detections: abs_path → [{label, rect, page_num, type}]
# Populated by list_form_fields() on scanned PDFs; read by fill_document().
_field_rect_cache: dict[str, list] = {}

PDF_DPI = 300  # DPI used for pdf2image renders — must match coord conversion

# EasyOCR reader — lazy-loaded on first scanned PDF, cached for process lifetime
_ocr_reader = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _open_pdf(path: str) -> fitz.Document:
    """Open a PDF; raise ValueError with a clear message if it can't be opened."""
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        raise ValueError(f"File not found: {path}")
    try:
        doc = fitz.open(path)
    except fitz.FileDataError as e:
        raise ValueError(f"Cannot open PDF (may be encrypted or corrupted): {e}")
    if doc.is_encrypted:
        raise ValueError(
            f"PDF is password-protected. Provide the password to open it: {path}"
        )
    return doc


def _detect_path(path: str) -> str:
    """
    Classify the PDF into one of three types:
      'acroform' — any page has widget annotations (interactive form fields)
      'digital'  — no widgets but pymupdf can extract meaningful text (> 50 chars)
      'scanned'  — no widgets and no extractable text (image-only, needs OCR)
    Mixed PDFs (some widget pages, some plain pages) → 'acroform'.
    """
    doc = _open_pdf(path)
    try:
        total_text = 0
        for page in doc:
            if list(page.widgets()):
                return "acroform"
            total_text += len(page.get_text("text").strip())
        return "digital" if total_text > 50 else "scanned"
    finally:
        doc.close()


def _list_acroform_fields(path: str) -> list[dict]:
    """
    Return a list of all AcroForm widget fields across all pages.
    Each entry: {name, type, value, page, rect}
    rect is in PDF points (x0, y0, x1, y1).
    """
    doc = _open_pdf(path)
    fields = []
    try:
        for page_num, page in enumerate(doc, start=1):
            for widget in page.widgets():
                fields.append({
                    "name": widget.field_name or f"field_{len(fields)+1}",
                    "type": _widget_type_name(widget.field_type),
                    "value": widget.field_value or "",
                    "page": page_num,
                    "rect": list(widget.rect),  # [x0, y0, x1, y1] in PDF points
                })
    finally:
        doc.close()
    return fields


def _widget_type_name(field_type: int) -> str:
    return {
        fitz.PDF_WIDGET_TYPE_TEXT: "text",
        fitz.PDF_WIDGET_TYPE_CHECKBOX: "checkbox",
        fitz.PDF_WIDGET_TYPE_RADIOBUTTON: "radio",
        fitz.PDF_WIDGET_TYPE_COMBOBOX: "dropdown",
        fitz.PDF_WIDGET_TYPE_LISTBOX: "listbox",
        fitz.PDF_WIDGET_TYPE_SIGNATURE: "signature",
    }.get(field_type, "unknown")


def px_to_pt(px: float, dpi: int = PDF_DPI) -> float:
    """Convert a pixel coordinate at render DPI to PDF points (72 pt/inch)."""
    return px * 72.0 / dpi


# ---------------------------------------------------------------------------
# Phase 3 — Scanned PDF OCR pipeline
# ---------------------------------------------------------------------------

def _get_ocr_reader():
    """Lazy-load EasyOCR reader on first call; cached for process lifetime."""
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(['en'], gpu=True, verbose=False)
    return _ocr_reader


def _pdf_to_images(path: str, dpi: int = PDF_DPI) -> list:
    """Convert all pages of a PDF to PIL images at the given DPI."""
    from pdf2image import convert_from_path
    return convert_from_path(path, dpi=dpi)


def _preprocess_image(image: Image.Image) -> Image.Image:
    """Convert to grayscale and sharpen — improves OCR on low-quality scans."""
    gray = image.convert("L")
    return gray.filter(ImageFilter.SHARPEN)


def _ocr_page(image: Image.Image) -> list:
    """
    Run EasyOCR on a single PIL image.
    Returns raw results: [(polygon, text, confidence), ...]
    polygon = [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]  (4-point, may be skewed)
    """
    reader = _get_ocr_reader()
    import numpy as np
    return reader.readtext(np.array(image))


def _polygon_to_rect(polygon: list) -> tuple[int, int, int, int]:
    """Convert a 4-point EasyOCR polygon to an axis-aligned bounding rect."""
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


def _ocr_to_word_list(image: Image.Image, conf_threshold: float = 0.5) -> list[dict]:
    """
    OCR a single page image and return a structured word list.
    Each entry: {text, x1, y1, x2, y2, confidence}
    Words below conf_threshold are dropped.
    Sorted top-to-bottom, left-to-right for correct reading order.
    """
    raw = _ocr_page(image)
    words = []
    for polygon, text, conf in raw:
        if conf < conf_threshold:
            continue
        x1, y1, x2, y2 = _polygon_to_rect(polygon)
        words.append({"text": text, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "confidence": conf})
    # Sort: primary top-to-bottom (y1), secondary left-to-right (x1)
    words.sort(key=lambda w: (w["y1"], w["x1"]))
    return words


def _build_word_map(path: str) -> dict[int, list[dict]]:
    """
    Run OCR on all pages of a scanned PDF.
    Returns {page_num (1-indexed): [word_list]} where each word has text + pixel bbox.
    """
    images = _pdf_to_images(path)
    word_map = {}
    for page_num, image in enumerate(images, start=1):
        preprocessed = _preprocess_image(image)
        word_map[page_num] = _ocr_to_word_list(preprocessed)
    return word_map


def _read_scanned_text(path: str) -> str:
    """
    Extract text from a scanned PDF via EasyOCR.
    Returns joined text with [Page N] markers, matching the format of _read_acroform_text.
    """
    word_map = _build_word_map(path)
    pages = []
    for page_num in sorted(word_map):
        words = word_map[page_num]
        if not words:
            continue
        text = " ".join(w["text"] for w in words)
        pages.append(f"[Page {page_num}]\n{text}")
    if not pages:
        return "No readable text found in this PDF. The scan may be too low quality or the page may be blank."
    return "\n\n".join(pages)


# ---------------------------------------------------------------------------
# Phase 4 — Geometric form field detection (OpenCV)
# ---------------------------------------------------------------------------

def _binarize(image) -> "np.ndarray":
    """Adaptive threshold → clean black/white numpy array for contour detection."""
    import cv2, numpy as np
    if hasattr(image, 'convert'):
        gray = np.array(image.convert("L"))
    elif len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=15, C=4
    )
    return binary


def _detect_horizontal_lines(binary, dpi: int = PDF_DPI) -> list[tuple]:
    """
    Find horizontal lines using HoughLinesP — these are underline form fields.
    Returns list of (x1, y1, x2, y2) tuples.
    Thresholds are DPI-aware (calibrated for 300 DPI, scale proportionally).
    """
    import cv2, numpy as np
    scale = dpi / 100.0
    min_line_len = int(150 * scale)   # ≥ 0.5" at target DPI
    max_gap = int(10 * scale)
    kernel_w = int(40 * scale)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, 1))
    h_lines_img = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    lines = cv2.HoughLinesP(
        h_lines_img, rho=1, theta=np.pi / 180,
        threshold=int(80 * scale), minLineLength=min_line_len, maxLineGap=max_gap
    )
    if lines is None:
        return []
    result = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if abs(y2 - y1) < abs(x2 - x1) * 0.09:  # near-horizontal only
            result.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
    return result


def _detect_rectangles(binary, dpi: int = PDF_DPI) -> list[tuple]:
    """
    Find rectangular box fields using contour detection.
    Returns list of (x, y, w, h) tuples that look like form input boxes.
    Thresholds are DPI-aware.
    """
    import cv2
    scale = dpi / 100.0
    min_w = int(120 * scale)   # ≥ 0.4" wide
    min_h = int(12 * scale)    # ≥ 0.04" tall
    max_h = int(100 * scale)   # ≤ 0.33" tall (taller = not a simple input field)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects = []
    h_img, w_img = binary.shape
    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
        if len(approx) != 4:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        if w < min_w or h < min_h or h > max_h:
            continue
        if w > w_img * 0.95:  # full-page-width → border, not a field
            continue
        aspect = w / max(h, 1)
        if aspect >= 2.0:
            rects.append((x, y, w, h))
    return rects


def _detect_checkboxes(binary, dpi: int = PDF_DPI) -> list[tuple]:
    """
    Find checkbox-sized square contours.
    Returns list of (x, y, w, h) tuples for checkbox-shaped regions.
    Thresholds are DPI-aware.
    """
    import cv2
    scale = dpi / 100.0
    min_sz = int(20 * scale)   # ≥ 0.07"
    max_sz = int(60 * scale)   # ≤ 0.2"
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    checkboxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if min_sz <= w <= max_sz and min_sz <= h <= max_sz:
            aspect = w / max(h, 1)
            if 0.7 <= aspect <= 1.4:
                checkboxes.append((x, y, w, h))
    return checkboxes


def _is_empty_region(region: tuple, word_list: list[dict], overlap_threshold: float = 0.3) -> bool:
    """
    Return True if no OCR word overlaps the region by more than overlap_threshold.
    region: (x1, y1, x2, y2) or (x, y, w, h) — both supported.
    """
    if len(region) == 4:
        rx1, ry1, rx2, ry2 = region
        if rx2 - rx1 < 50:  # treat as (x, y, w, h)
            rx1, ry1, rx2, ry2 = region[0], region[1], region[0]+region[2], region[1]+region[3]
    else:
        return True

    r_area = max((rx2 - rx1) * (ry2 - ry1), 1)
    for word in word_list:
        wx1, wy1, wx2, wy2 = word["x1"], word["y1"], word["x2"], word["y2"]
        # Intersection
        ix1, iy1 = max(rx1, wx1), max(ry1, wy1)
        ix2, iy2 = min(rx2, wx2), min(ry2, wy2)
        if ix2 > ix1 and iy2 > iy1:
            intersection = (ix2 - ix1) * (iy2 - iy1)
            if intersection / r_area > overlap_threshold:
                return False
    return True


def _find_label_for_field(field_rect: tuple, word_list: list[dict], search_px: int = 200) -> str:
    """
    Find the nearest word to the left of or above the field rect — that's the label.
    field_rect: (x1, y1, x2, y2)
    Returns label string, or empty string if none found.
    """
    fx1, fy1, fx2, fy2 = field_rect
    fy_mid = (fy1 + fy2) / 2

    best_word = None
    best_dist = float("inf")

    for word in word_list:
        wx1, wy1, wx2, wy2 = word["x1"], word["y1"], word["x2"], word["y2"]
        wy_mid = (wy1 + wy2) / 2

        # Word to the left: right edge of word is left of field left edge
        if wx2 <= fx1 and abs(wy_mid - fy_mid) < (fy2 - fy1 + 20):
            dist = fx1 - wx2
            if dist < best_dist and dist < search_px:
                best_dist = dist
                best_word = word["text"]

        # Word directly above: bottom of word is above top of field, x overlaps
        elif wy2 <= fy1 and wx1 < fx2 and wx2 > fx1:
            dist = fy1 - wy2
            if dist < best_dist and dist < search_px:
                best_dist = dist
                best_word = word["text"]

    return best_word or ""


def _nms_lines(lines: list[tuple], y_tolerance: int = 8) -> list[tuple]:
    """
    Merge horizontal lines that are within y_tolerance pixels of each other
    and have overlapping x extents — they are the same field edge.
    """
    if not lines:
        return []
    # Sort by y
    sorted_lines = sorted(lines, key=lambda l: l[1])
    merged = []
    used = [False] * len(sorted_lines)
    for i, a in enumerate(sorted_lines):
        if used[i]:
            continue
        ax1, ay1, ax2, ay2 = a
        group = [a]
        for j, b in enumerate(sorted_lines):
            if i == j or used[j]:
                continue
            bx1, by1, bx2, by2 = b
            if abs(ay1 - by1) <= y_tolerance:
                # Check x overlap
                if bx1 <= ax2 and bx2 >= ax1:
                    group.append(b)
                    used[j] = True
        # Merge group into one line (union of x extents, median y)
        x1 = min(l[0] for l in group)
        x2 = max(l[2] for l in group)
        y = int(sum(l[1] for l in group) / len(group))
        merged.append((x1, y, x2, y))
    return merged


def _nms_rects(rects: list[tuple], iou_threshold: float = 0.3) -> list[tuple]:
    """Non-maximum suppression — remove duplicate overlapping rectangles."""
    if not rects:
        return []
    kept = []
    used = [False] * len(rects)
    # Sort by area descending
    rects_sorted = sorted(rects, key=lambda r: r[2] * r[3] if len(r) == 4 else (r[2]-r[0])*(r[3]-r[1]), reverse=True)
    for i, a in enumerate(rects_sorted):
        if used[i]:
            continue
        kept.append(a)
        ax1 = a[0]; ay1 = a[1]
        ax2 = a[0]+a[2] if len(a)==4 else a[2]
        ay2 = a[1]+a[3] if len(a)==4 else a[3]
        a_area = max((ax2-ax1)*(ay2-ay1), 1)
        for j, b in enumerate(rects_sorted):
            if i == j or used[j]:
                continue
            bx1 = b[0]; by1 = b[1]
            bx2 = b[0]+b[2] if len(b)==4 else b[2]
            by2 = b[1]+b[3] if len(b)==4 else b[3]
            ix1, iy1 = max(ax1, bx1), max(ay1, by1)
            ix2, iy2 = min(ax2, bx2), min(ay2, by2)
            if ix2 > ix1 and iy2 > iy1:
                inter = (ix2-ix1)*(iy2-iy1)
                b_area = max((bx2-bx1)*(by2-by1), 1)
                iou = inter / (a_area + b_area - inter)
                if iou > iou_threshold:
                    used[j] = True
    return kept


def _detect_empty_fields_geometric(image, word_list: list[dict], page_num: int = 1, dpi: int = PDF_DPI) -> list[dict]:
    """
    Detect empty form fields geometrically using OpenCV.
    Combines underline detection, rectangle detection, and checkbox detection.
    Returns list of: {label, type, rect (x1,y1,x2,y2 pixels), page}
    """
    binary = _binarize(image)
    fields = []

    # --- Horizontal underline fields ---
    img_w = binary.shape[1]
    lines = _detect_horizontal_lines(binary, dpi=dpi)
    # Deduplicate nearby parallel lines (same field detected multiple times)
    lines = _nms_lines(lines, y_tolerance=int(15 * dpi / 100))
    for (x1, y1, x2, y2) in lines:
        # Skip full-page-width lines — those are section dividers, not fields
        if (x2 - x1) > img_w * 0.80:
            continue
        pad = int(25 * dpi / 100)
        region = (x1, max(0, y1 - pad), x2, y2 + 5)
        if _is_empty_region(region, word_list):
            label = _find_label_for_field((x1, y1, x2, y2), word_list)
            fields.append({
                "label": label,
                "type": "underline",
                "rect": region,
                "page": page_num,
            })

    # --- Rectangle box fields ---
    rects = _detect_rectangles(binary, dpi=dpi)
    rects = _nms_rects(rects)
    for (x, y, w, h) in rects:
        rect = (x, y, x + w, y + h)
        if _is_empty_region(rect, word_list):
            label = _find_label_for_field(rect, word_list)
            fields.append({
                "label": label,
                "type": "textbox",
                "rect": rect,
                "page": page_num,
            })

    # --- Checkbox fields ---
    checkboxes = _detect_checkboxes(binary, dpi=dpi)
    for (x, y, w, h) in checkboxes:
        rect = (x, y, x + w, y + h)
        if _is_empty_region(rect, word_list):
            label = _find_label_for_field(rect, word_list)
            fields.append({
                "label": label,
                "type": "checkbox",
                "rect": rect,
                "page": page_num,
            })

    return fields


def _draw_detections(image, fields: list[dict], output_path: str):
    """Debug helper: draw detected fields on image and save as PNG."""
    import cv2, numpy as np
    colors = {"underline": (255, 100, 0), "textbox": (0, 200, 0), "checkbox": (0, 0, 255)}
    img = np.array(image.convert("RGB") if hasattr(image, 'convert') else image)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    for f in fields:
        x1, y1, x2, y2 = f["rect"]
        color = colors.get(f["type"], (128, 128, 128))
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        label = f.get("label", "")[:30]
        if label:
            cv2.putText(img, label, (x1, max(y1 - 5, 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    cv2.imwrite(output_path, img)


# ---------------------------------------------------------------------------
# Phase 5 — Semantic field understanding (LayoutLMv3)
# ---------------------------------------------------------------------------

# Lazy-loaded LayoutLMv3 processor + model — cached for process lifetime
_layoutlm_processor = None
_layoutlm_model = None

_LAYOUTLM_MODEL = "nielsr/layoutlmv3-finetuned-funsd"

# Label IDs from model.config.id2label
_LABEL_QUESTION = {3, 4}   # B-QUESTION, I-QUESTION
_LABEL_ANSWER   = {5, 6}   # B-ANSWER,   I-ANSWER
_LABEL_HEADER   = {1, 2}   # B-HEADER,   I-HEADER


def _load_layoutlm():
    """Lazy-load LayoutLMv3 processor + model to GPU. Cached after first call."""
    global _layoutlm_processor, _layoutlm_model
    if _layoutlm_processor is None:
        import torch
        from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
        # apply_ocr=False: we supply our own EasyOCR words+boxes, not Tesseract
        _layoutlm_processor = LayoutLMv3Processor.from_pretrained(_LAYOUTLM_MODEL, apply_ocr=False)
        _layoutlm_model = LayoutLMv3ForTokenClassification.from_pretrained(_LAYOUTLM_MODEL)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _layoutlm_model = _layoutlm_model.to(device)
        _layoutlm_model.eval()
    return _layoutlm_processor, _layoutlm_model


def _normalize_bbox(bbox: tuple, img_w: int, img_h: int) -> list[int]:
    """Normalize pixel bbox to 0–1000 range required by LayoutLMv3."""
    x1, y1, x2, y2 = bbox
    return [
        int(1000 * x1 / max(img_w, 1)),
        int(1000 * y1 / max(img_h, 1)),
        int(1000 * x2 / max(img_w, 1)),
        int(1000 * y2 / max(img_h, 1)),
    ]


def _prepare_layoutlm_input(image, word_list: list[dict], processor):
    """
    Tokenize words + normalized bboxes into LayoutLMv3 model inputs.
    Handles the 512-token limit by truncating (long pages are windowed in _run_layoutlm).
    Returns encoded inputs dict on the model's device.
    """
    import torch
    img_w, img_h = image.size if hasattr(image, 'size') else (image.shape[1], image.shape[0])

    words = [w["text"] for w in word_list]
    boxes = [_normalize_bbox((w["x1"], w["y1"], w["x2"], w["y2"]), img_w, img_h) for w in word_list]

    if not words:
        return None

    # Convert grayscale PIL to RGB (LayoutLMv3 requires 3-channel image)
    if hasattr(image, 'convert'):
        rgb = image.convert("RGB")
    else:
        from PIL import Image as PILImage
        import numpy as np
        rgb = PILImage.fromarray(image).convert("RGB")

    encoding = processor(
        rgb,
        words,
        boxes=boxes,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding="max_length",
    )
    device = next(_layoutlm_model.parameters()).device
    return {k: v.to(device) for k, v in encoding.items()}


def _run_layoutlm(image, word_list: list[dict]) -> list[int] | None:
    """
    Run LayoutLMv3 inference on a single page image + word list.
    Returns per-word label IDs aligned to word_list, or None on failure.

    The fast tokenizer (TokenizersBackend) does not output `bbox`, so we build
    it manually: tokenize words → get word_ids → map each token to its word's
    normalized bbox. Special tokens get [0,0,0,0].
    """
    if not word_list:
        return None
    try:
        import torch
        processor, model = _load_layoutlm()
        device = next(model.parameters()).device

        img_w, img_h = image.size if hasattr(image, 'size') else (image.shape[1], image.shape[0])
        words = [w["text"] for w in word_list]
        norm_boxes = [_normalize_bbox((w["x1"], w["y1"], w["x2"], w["y2"]), img_w, img_h) for w in word_list]

        if hasattr(image, 'convert'):
            rgb = image.convert("RGB")
        else:
            from PIL import Image as PILImage
            rgb = PILImage.fromarray(image).convert("RGB")

        # Tokenize — fast tokenizer won't include bbox, we add it manually
        tok_enc = processor.tokenizer(
            words, boxes=norm_boxes, is_split_into_words=True,
            return_tensors="pt", truncation=True, max_length=512, padding="max_length",
        )
        word_ids = tok_enc.word_ids(batch_index=0)

        # Build bbox tensor: one [x1,y1,x2,y2] per token; [0,0,0,0] for special tokens
        bbox_list = []
        for wid in word_ids:
            bbox_list.append(norm_boxes[wid] if wid is not None else [0, 0, 0, 0])
        bbox_tensor = torch.tensor([bbox_list], dtype=torch.long)  # (1, seq_len, 4)

        # Image pixel values
        img_enc = processor.image_processor(rgb, return_tensors="pt")

        inputs = {
            "input_ids":      tok_enc["input_ids"].to(device),
            "attention_mask": tok_enc["attention_mask"].to(device),
            "bbox":           bbox_tensor.to(device),
            "pixel_values":   img_enc["pixel_values"].to(device),
        }

        with torch.no_grad():
            outputs = model(**inputs)

        predictions = outputs.logits.argmax(-1).squeeze(0).tolist()

        # First-token-wins: one label per word
        word_labels = {}
        for token_idx, wid in enumerate(word_ids):
            if wid is not None and wid not in word_labels:
                word_labels[wid] = predictions[token_idx]

        return [word_labels.get(i, 0) for i in range(len(word_list))]

    except Exception:
        return None


def _extract_entities(word_labels: list[int], word_list: list[dict]) -> list[dict]:
    """
    Group consecutive same-class tokens into entity spans.
    Returns list of: {label_type, text, words, bbox (x1,y1,x2,y2)}
    label_type: 'QUESTION', 'ANSWER', 'HEADER', 'OTHER'
    """
    if not word_labels:
        return []

    _label_name = {0: "OTHER", 1: "HEADER", 2: "HEADER",
                   3: "QUESTION", 4: "QUESTION", 5: "ANSWER", 6: "ANSWER"}

    entities = []
    current_type = None
    current_words = []

    for i, (label_id, word) in enumerate(zip(word_labels, word_list)):
        ltype = _label_name.get(label_id, "OTHER")
        if ltype == current_type:
            current_words.append(word)
        else:
            if current_words and current_type and current_type != "OTHER":
                entities.append(_make_entity(current_type, current_words))
            current_type = ltype
            current_words = [word]

    if current_words and current_type and current_type != "OTHER":
        entities.append(_make_entity(current_type, current_words))

    return entities


def _make_entity(label_type: str, words: list[dict]) -> dict:
    x1 = min(w["x1"] for w in words)
    y1 = min(w["y1"] for w in words)
    x2 = max(w["x2"] for w in words)
    y2 = max(w["y2"] for w in words)
    return {
        "label_type": label_type,
        "text": " ".join(w["text"] for w in words),
        "words": words,
        "bbox": (x1, y1, x2, y2),
    }


def _match_questions_to_empty_fields(entities: list[dict], proximity_px: int = 300) -> list[dict]:
    """
    Find QUESTION entities that have no spatially adjacent ANSWER entity.
    A QUESTION with no nearby ANSWER = empty field.
    Returns list of: {label, type, rect (x1,y1,x2,y2)}
    proximity_px is the maximum distance (in pixels) to look for an adjacent answer.
    """
    questions = [e for e in entities if e["label_type"] == "QUESTION"]
    answers   = [e for e in entities if e["label_type"] == "ANSWER"]

    empty_fields = []
    for q in questions:
        qx1, qy1, qx2, qy2 = q["bbox"]
        qy_mid = (qy1 + qy2) / 2

        has_answer = False
        for a in answers:
            ax1, ay1, ax2, ay2 = a["bbox"]
            ay_mid = (ay1 + ay2) / 2
            # Answer is to the right on the same line, or just below
            same_row = abs(ay_mid - qy_mid) < max((qy2 - qy1) * 1.5, 30)
            right_of = ax1 >= qx1 and ax1 - qx2 < proximity_px
            below = ay1 >= qy2 and ay1 - qy2 < proximity_px and ax1 < qx2
            if same_row and right_of or below:
                has_answer = True
                break

        if not has_answer:
            # Estimated field rect: span to the right of the question label
            field_x1 = qx2 + 10
            field_y1 = qy1
            field_x2 = qx2 + 400  # estimated field width
            field_y2 = qy2
            empty_fields.append({
                "label": q["text"],
                "type": "semantic",
                "rect": (field_x1, field_y1, field_x2, field_y2),
            })

    return empty_fields


def _detect_empty_fields_semantic(image, word_list: list[dict], page_num: int = 1) -> list[dict]:
    """
    Full semantic pipeline: LayoutLMv3 → entity extraction → empty field matching.
    Returns list of: {label, type, rect, page, confidence}
    Falls back to empty list on any failure (geometric detection still runs).
    """
    try:
        word_labels = _run_layoutlm(image, word_list)
        if word_labels is None:
            return []
        entities = _extract_entities(word_labels, word_list)
        fields = _match_questions_to_empty_fields(entities)
        for f in fields:
            f["page"] = page_num
            f["confidence"] = "semantic"
        return fields
    except Exception:
        return []


def _merge_fields(geometric: list[dict], semantic: list[dict], proximity_px: int = 60) -> list[dict]:
    """
    Merge geometric and semantic field lists, deduplicating by proximity.
    Semantic fields that overlap an existing geometric field are dropped (geometric has exact rect).
    Semantic-only fields (no geometric match) are added with estimated rects.
    """
    merged = list(geometric)
    for sf in semantic:
        sx1, sy1, sx2, sy2 = sf["rect"]
        s_cx = (sx1 + sx2) / 2
        s_cy = (sy1 + sy2) / 2
        # Check if a geometric field is nearby
        duplicate = False
        for gf in geometric:
            gx1, gy1, gx2, gy2 = gf["rect"]
            g_cx = (gx1 + gx2) / 2
            g_cy = (gy1 + gy2) / 2
            if abs(s_cx - g_cx) < proximity_px and abs(s_cy - g_cy) < proximity_px:
                # Geometric already covers this — enrich label if geometric has none
                if not gf.get("label") and sf.get("label"):
                    gf["label"] = sf["label"]
                duplicate = True
                break
        if not duplicate:
            merged.append(sf)
    return merged


# ---------------------------------------------------------------------------
# Phase 6 — Scanned PDF text overlay fill helpers
# ---------------------------------------------------------------------------

def _run_scanned_detection(path: str) -> list[dict]:
    """
    Run the full scanned detection pipeline (OCR + geometric + semantic) on a PDF.
    Returns merged field list and populates _field_rect_cache[path].
    """
    abs_path = os.path.abspath(path)
    images = _pdf_to_images(path)
    all_fields = []
    for page_num, image in enumerate(images, start=1):
        pre = _preprocess_image(image)
        word_list = _ocr_to_word_list(pre)
        geo = _detect_empty_fields_geometric(image, word_list, page_num=page_num, dpi=PDF_DPI)
        sem = _detect_empty_fields_semantic(image, word_list, page_num=page_num)
        merged = _merge_fields(geo, sem)
        for f in merged:
            if "page" not in f:
                f["page"] = page_num
        all_fields.extend(merged)
    _field_rect_cache[abs_path] = all_fields
    return all_fields


def _blank_field_region(page: "fitz.Page", rect_pt: tuple):
    """Draw a filled white rectangle over a field region to erase underlines/boxes."""
    import fitz
    r = fitz.Rect(rect_pt[0], rect_pt[1], rect_pt[2], rect_pt[3])
    page.draw_rect(r, color=(1, 1, 1), fill=(1, 1, 1))


def _fit_font_size(rect_pt: tuple, text: str, max_pt: float = 12.0, min_pt: float = 7.0) -> float:
    """Choose the largest font size (pt) that fits text within the field height."""
    field_h = rect_pt[3] - rect_pt[1]
    field_w = rect_pt[2] - rect_pt[0]
    # Rough estimate: ~0.6 width per char at 1pt; cap to field height * 0.8
    size_by_height = field_h * 0.75
    chars = max(len(text), 1)
    size_by_width = (field_w * 1.4) / chars
    size = min(size_by_height, size_by_width, max_pt)
    return max(size, min_pt)


def _wrap_text(text: str, rect_pt: tuple, font_size: float, chars_per_pt: float = 0.6) -> list[str]:
    """Split text into lines that fit within the field width."""
    field_w = rect_pt[2] - rect_pt[0]
    max_chars = max(int(field_w / (font_size * chars_per_pt)), 1)
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if len(test) <= max_chars:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _overlay_text(page: "fitz.Page", rect_pt: tuple, text: str, is_checkbox: bool = False):
    """
    Insert text at the given PDF-point rect.
    Blanks the field region first, then writes the text.
    Handles multi-line wrapping for tall fields.
    """
    import fitz
    _blank_field_region(page, rect_pt)
    x1, y1, x2, y2 = rect_pt
    field_h = y2 - y1

    if is_checkbox:
        # Draw a checkmark symbol centred in the box
        cx = (x1 + x2) / 2 - 4
        cy = (y1 + y2) / 2 + 4
        page.insert_text((cx, cy), "✓", fontsize=min(field_h * 0.8, 12), color=(0, 0, 0))
        return

    font_size = _fit_font_size(rect_pt, text)
    lines = _wrap_text(text, rect_pt, font_size)
    line_h = font_size * 1.2
    y_start = y1 + font_size  # baseline of first line

    for i, line in enumerate(lines):
        y = y_start + i * line_h
        if y > y2 + font_size:  # don't write outside the field
            break
        page.insert_text((x1 + 2, y), line, fontsize=font_size, color=(0, 0, 0))


def _fill_scanned(path: str, fields: dict, output_path: str) -> str:
    """
    Fill a scanned PDF by overlaying text at detected field pixel positions.
    Reads pixel rects from _field_rect_cache (populated by list_form_fields).
    Converts pixel coords → PDF points via px_to_pt().
    """
    abs_path = os.path.abspath(path)
    cached = _field_rect_cache.get(abs_path)
    if cached is None:
        # Cache miss — run detection now (list_form_fields was skipped)
        cached = _run_scanned_detection(path)

    if not cached:
        return "No form fields were detected in this scanned PDF. Try list_form_fields first to inspect the document."

    try:
        doc = _open_pdf(path)
    except ValueError as e:
        return str(e)

    # Build a case-insensitive lookup of field label → value
    fill_map = {k.lower().strip(): v for k, v in fields.items()}
    filled = []
    not_found = list(fields.keys())

    try:
        for field in cached:
            label = (field.get("label") or "").lower().strip()
            value = fill_map.get(label)
            if value is None:
                # Try partial match
                for k, v in fill_map.items():
                    if k in label or label in k:
                        value = v
                        break
            if value is None:
                continue

            page_num = field.get("page", 1) - 1  # 0-indexed for pymupdf
            page = doc[page_num]
            px_rect = field["rect"]  # (x1, y1, x2, y2) in pixels at PDF_DPI
            pt_rect = tuple(px_to_pt(c) for c in px_rect)

            is_cb = field.get("type") == "checkbox"
            _overlay_text(page, pt_rect, str(value), is_checkbox=is_cb)
            filled.append(field.get("label") or label)
            not_found = [n for n in not_found if n.lower().strip() != label]

        doc.save(output_path)
    finally:
        doc.close()

    result = f"Filled {len(filled)} field(s) and saved to: {output_path}"
    if not_found:
        result += f"\nFields not matched: {', '.join(not_found)}"
    return result


# ---------------------------------------------------------------------------
# Public tools (complete — all three tools fully wired for all PDF types)
# ---------------------------------------------------------------------------

def list_form_fields(path: str) -> str:
    """
    Inspect a PDF for fillable form fields.
    AcroForm: widget list, instant.
    Digital (no widgets): tells user to use read_document.
    Scanned: runs OCR + geometric + semantic detection; caches rects for fill_document.
    """
    path = os.path.expanduser(path)
    try:
        pdf_type = _detect_path(path)
    except ValueError as e:
        return str(e)

    if pdf_type == "digital":
        return "This is a plain digital PDF with no fillable form fields (e.g. a resume or report). Use read_document to read its contents."

    if pdf_type == "acroform":
        try:
            fields = _list_acroform_fields(path)
        except ValueError as e:
            return str(e)
        if not fields:
            return "No fillable fields found in this PDF."
        lines = [f"Found {len(fields)} fillable field(s):\n"]
        for i, f in enumerate(fields, 1):
            val = f"(current: {f['value']!r})" if f["value"] else "(empty)"
            lines.append(f"  {i}. {f['name']} [{f['type']}] — page {f['page']} {val}")
        return "\n".join(lines)

    # Scanned path — run full detection pipeline and cache results
    try:
        fields = _run_scanned_detection(path)
    except Exception as e:
        return f"Scanned PDF field detection failed: {e}"

    if not fields:
        return "No form fields detected in this scanned PDF. The scan may be too low quality or the page has no standard form elements."

    lines = [f"Found {len(fields)} potential form field(s) (scanned PDF):\n"]
    for i, f in enumerate(fields, 1):
        label = f.get("label") or "(unlabeled)"
        ftype = f.get("type", "unknown")
        page  = f.get("page", 1)
        lines.append(f"  {i}. {label} [{ftype}] — page {page}")
    lines.append("\nNote: Use fill_document to fill these fields by label name.")
    return "\n".join(lines)


def read_document(path: str) -> str:
    """
    Extract and return all text from a PDF.
    AcroForm and plain digital PDFs: uses pymupdf text extraction (fast).
    Scanned PDFs: OCR pipeline not yet implemented (Phase 3).
    """
    path = os.path.expanduser(path)
    try:
        pdf_type = _detect_path(path)
    except ValueError as e:
        return str(e)

    if pdf_type in ("acroform", "digital"):
        return _read_acroform_text(path)

    return _read_scanned_text(path)


def _read_acroform_text(path: str) -> str:
    """Extract clean text from a digital PDF using pymupdf."""
    try:
        doc = _open_pdf(path)
    except ValueError as e:
        return str(e)
    pages = []
    try:
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if text:
                pages.append(f"[Page {page_num}]\n{text}")
    finally:
        doc.close()
    if not pages:
        return "No readable text found in this PDF."
    return "\n\n".join(pages)


def fill_document(path: str, fields: dict, output_path: str = None) -> str:
    """
    Fill a PDF form with the provided field values.
    fields: {field_name: value, ...}
    output_path: where to save the result (default: original_name_filled.pdf)
    AcroForm PDFs: writes to widget objects.
    Scanned PDFs: not yet implemented (Phase 6).
    """
    path = os.path.expanduser(path)

    # Auto-generate output path
    if not output_path:
        base, ext = os.path.splitext(path)
        output_path = f"{base}_filled{ext}"
    output_path = os.path.expanduser(output_path)

    # ALLOWED_DIRS check
    allowed_dirs = [os.path.expanduser(d) for d in os.environ.get("ALLOWED_DIRS", "/home").split(",")]
    if not any(os.path.abspath(output_path).startswith(d) for d in allowed_dirs):
        return f"Output path {output_path!r} is outside allowed directories. Choose a path inside {allowed_dirs}."

    try:
        pdf_type = _detect_path(path)
    except ValueError as e:
        return str(e)

    if pdf_type == "digital":
        return "This PDF has no fillable form fields. Use list_form_fields to check, or read_document to read its contents."

    if pdf_type == "acroform":
        return _fill_acroform(path, fields, output_path)

    return _fill_scanned(path, fields, output_path)


def _fill_acroform(path: str, fields: dict, output_path: str) -> str:
    """Fill AcroForm widget fields and save to output_path."""
    try:
        doc = _open_pdf(path)
    except ValueError as e:
        return str(e)

    filled = []
    not_found = []
    try:
        fields_lower = {k.lower(): v for k, v in fields.items()}
        for page in doc:
            for widget in page.widgets():
                name = widget.field_name or ""
                value = fields.get(name) or fields_lower.get(name.lower())
                if value is None:
                    continue
                if widget.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                    widget.field_value = "Yes" if str(value).lower() in ("yes", "true", "1", "x") else "Off"
                else:
                    widget.field_value = str(value)
                widget.update()
                filled.append(name)

        for name in fields:
            if name not in filled and name.lower() not in [f.lower() for f in filled]:
                not_found.append(name)

        doc.save(output_path)
    finally:
        doc.close()

    result = f"Filled {len(filled)} field(s) and saved to: {output_path}"
    if not_found:
        result += f"\nFields not found in PDF: {', '.join(not_found)}"
    return result
